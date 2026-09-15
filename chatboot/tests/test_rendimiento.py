#!/usr/bin/env python3
"""Recolector de metricas de rendimiento para el contenedor de chatboot.

Uso recomendado desde la raiz del proyecto:

    python chatboot/tests/test_rendimiento.py

El script toma muestras del contenedor Docker y del sistema host. Se detiene
cuando pasan 5 minutos sin actividad de red, logs o CPU en el contenedor, y
exporta un archivo Excel .xlsx junto con graficos SVG.

Nota: Docker reporta `CPUPerc` como uso agregado sobre todos los nucleos del
host, asi que puede superar 100% en maquinas multi-core. El reporte conserva
ese valor crudo para deteccion de actividad y ademas publica una version
normalizada respecto al total de CPUs del host para facilitar la lectura.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


DEFAULT_CONTAINER = "riobambago-chatboot"
DEFAULT_IDLE_SECONDS = 300
DEFAULT_INTERVAL_SECONDS = 5
DEFAULT_CPU_ACTIVITY_PERCENT = 5.0
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "resultados_rendimiento"
HOST_CPU_COUNT = os.cpu_count() or 1


@dataclass
class SystemCpuSnapshot:
    idle: int
    total: int


@dataclass
class Sample:
    timestamp: str
    elapsed_seconds: float
    container_cpu_percent: float
    container_cpu_docker_percent: float
    container_cpu_limit_cores: float
    container_cpu_budget_percent: float
    container_mem_usage_mb: float
    container_mem_limit_mb: float
    container_mem_percent: float
    container_net_rx_mb: float
    container_net_tx_mb: float
    container_net_rx_delta_mb: float
    container_net_tx_delta_mb: float
    container_block_read_mb: float
    container_block_write_mb: float
    container_pids: int
    system_cpu_percent: float
    system_mem_used_mb: float
    system_mem_total_mb: float
    system_mem_percent: float
    activity_detected: bool
    activity_reasons: str
    seconds_since_activity: float


def run_command(args: list[str]) -> str:
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"No se encontro el comando requerido: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"Fallo comando {' '.join(args)}: {detail}") from exc
    return completed.stdout.strip()


def docker_container_exists(container: str) -> bool:
    try:
        run_command(["docker", "inspect", container])
    except RuntimeError:
        return False
    return True


def parse_percent(value: str) -> float:
    return float(value.strip().replace("%", "").replace(",", ".") or 0)


def parse_size_to_mb(value: str) -> float:
    text = value.strip().replace(",", ".")
    match = re.match(r"^([0-9.]+)\s*([KMGT]?i?B|B)?$", text, re.IGNORECASE)
    if not match:
        return 0.0
    number = float(match.group(1))
    unit = (match.group(2) or "B").lower()
    multipliers = {
        "b": 1 / (1024 * 1024),
        "kb": 1 / 1024,
        "kib": 1 / 1024,
        "mb": 1,
        "mib": 1,
        "gb": 1024,
        "gib": 1024,
        "tb": 1024 * 1024,
        "tib": 1024 * 1024,
    }
    return number * multipliers.get(unit, 0)


def parse_pair_to_mb(value: str) -> tuple[float, float]:
    left, _, right = value.partition("/")
    return parse_size_to_mb(left), parse_size_to_mb(right)


def parse_cpuset_cpus(value: str) -> float:
    text = value.strip()
    if not text:
        return 0.0
    count = 0
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError:
                continue
            if end >= start:
                count += end - start + 1
        else:
            try:
                int(part)
            except ValueError:
                continue
            count += 1
    return float(count)


def read_container_cpu_limit_cores(container: str) -> float:
    raw = run_command(["docker", "inspect", container, "--format", "{{json .HostConfig}}"])
    data = json.loads(raw)
    nano_cpus = int(data.get("NanoCpus", 0) or 0)
    if nano_cpus > 0:
        return nano_cpus / 1_000_000_000
    cpu_quota = int(data.get("CpuQuota", 0) or 0)
    cpu_period = int(data.get("CpuPeriod", 0) or 0)
    if cpu_quota > 0 and cpu_period > 0:
        return cpu_quota / cpu_period
    cpuset_cores = parse_cpuset_cpus(str(data.get("CpusetCpus", "") or ""))
    if cpuset_cores > 0:
        return cpuset_cores
    return float(HOST_CPU_COUNT)


def read_docker_stats(container: str) -> dict[str, float | int]:
    raw = run_command(["docker", "stats", container, "--no-stream", "--format", "{{json .}}"])
    data = json.loads(raw)
    mem_usage, mem_limit = parse_pair_to_mb(data.get("MemUsage", "0B / 0B"))
    net_rx, net_tx = parse_pair_to_mb(data.get("NetIO", "0B / 0B"))
    block_read, block_write = parse_pair_to_mb(data.get("BlockIO", "0B / 0B"))
    return {
        "container_cpu_docker_percent": parse_percent(data.get("CPUPerc", "0%")),
        "container_mem_usage_mb": mem_usage,
        "container_mem_limit_mb": mem_limit,
        "container_mem_percent": parse_percent(data.get("MemPerc", "0%")),
        "container_net_rx_mb": net_rx,
        "container_net_tx_mb": net_tx,
        "container_block_read_mb": block_read,
        "container_block_write_mb": block_write,
        "container_pids": int(data.get("PIDs", 0) or 0),
    }


def read_cpu_snapshot() -> SystemCpuSnapshot:
    with open("/proc/stat", "r", encoding="utf-8") as file:
        fields = file.readline().split()[1:]
    values = [int(value) for value in fields]
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return SystemCpuSnapshot(idle=idle, total=sum(values))


def cpu_percent(previous: SystemCpuSnapshot, current: SystemCpuSnapshot) -> float:
    idle_delta = current.idle - previous.idle
    total_delta = current.total - previous.total
    if total_delta <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))


def read_memory() -> tuple[float, float, float]:
    values: dict[str, int] = {}
    with open("/proc/meminfo", "r", encoding="utf-8") as file:
        for line in file:
            key, raw_value = line.split(":", 1)
            values[key] = int(raw_value.strip().split()[0])
    total_mb = values.get("MemTotal", 0) / 1024
    available_mb = values.get("MemAvailable", 0) / 1024
    used_mb = max(0.0, total_mb - available_mb)
    percent = (used_mb / total_mb * 100) if total_mb else 0.0
    return used_mb, total_mb, percent


def logs_changed(container: str, since_epoch: float) -> bool:
    since_arg = f"{since_epoch:.9f}"
    try:
        completed = subprocess.run(
            ["docker", "logs", "--since", since_arg, container],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    output = f"{completed.stdout}\n{completed.stderr}"
    return bool(output.strip())


def network_changed(
    previous: tuple[float, float] | None,
    current: tuple[float, float],
    min_delta_mb: float,
) -> bool:
    if previous is None:
        return False
    rx_delta = current[0] - previous[0]
    tx_delta = current[1] - previous[1]
    return (rx_delta + tx_delta) >= min_delta_mb


def network_deltas(
    previous: tuple[float, float] | None,
    current: tuple[float, float],
) -> tuple[float, float]:
    if previous is None:
        return 0.0, 0.0
    return max(0.0, current[0] - previous[0]), max(0.0, current[1] - previous[1])


def make_sample(
    *,
    start_time: float,
    container: str,
    container_cpu_limit_cores: float,
    previous_cpu: SystemCpuSnapshot,
    previous_net: tuple[float, float] | None,
    previous_log_check: float,
    min_network_delta_mb: float,
    cpu_activity_percent: float,
    detect_logs: bool,
    detect_network: bool,
    detect_cpu: bool,
    last_activity: float,
) -> tuple[Sample, SystemCpuSnapshot, tuple[float, float], float, float]:
    stats = read_docker_stats(container)
    container_cpu_docker_percent = float(stats["container_cpu_docker_percent"])
    container_cpu_percent = container_cpu_docker_percent / HOST_CPU_COUNT
    cpu_limit_cores = container_cpu_limit_cores if container_cpu_limit_cores > 0 else float(HOST_CPU_COUNT)
    container_cpu_budget_percent = container_cpu_docker_percent / cpu_limit_cores
    current_cpu = read_cpu_snapshot()
    system_cpu = cpu_percent(previous_cpu, current_cpu)
    mem_used, mem_total, mem_percent = read_memory()
    current_net = (
        float(stats["container_net_rx_mb"]),
        float(stats["container_net_tx_mb"]),
    )
    rx_delta, tx_delta = network_deltas(previous_net, current_net)
    activity_reasons: list[str] = []
    if detect_network and network_changed(previous_net, current_net, min_network_delta_mb):
        activity_reasons.append("red")
    if detect_logs and logs_changed(container, previous_log_check):
        activity_reasons.append("logs")
    if detect_cpu and container_cpu_docker_percent >= cpu_activity_percent:
        activity_reasons.append("cpu")

    activity = bool(activity_reasons)

    now = time.time()
    if activity:
        last_activity = now

    sample = Sample(
        timestamp=datetime.fromtimestamp(now).isoformat(timespec="seconds"),
        elapsed_seconds=round(now - start_time, 3),
        container_cpu_percent=container_cpu_percent,
        container_cpu_docker_percent=container_cpu_docker_percent,
        container_cpu_limit_cores=cpu_limit_cores,
        container_cpu_budget_percent=container_cpu_budget_percent,
        container_mem_usage_mb=float(stats["container_mem_usage_mb"]),
        container_mem_limit_mb=float(stats["container_mem_limit_mb"]),
        container_mem_percent=float(stats["container_mem_percent"]),
        container_net_rx_mb=current_net[0],
        container_net_tx_mb=current_net[1],
        container_net_rx_delta_mb=rx_delta,
        container_net_tx_delta_mb=tx_delta,
        container_block_read_mb=float(stats["container_block_read_mb"]),
        container_block_write_mb=float(stats["container_block_write_mb"]),
        container_pids=int(stats["container_pids"]),
        system_cpu_percent=system_cpu,
        system_mem_used_mb=mem_used,
        system_mem_total_mb=mem_total,
        system_mem_percent=mem_percent,
        activity_detected=activity,
        activity_reasons=",".join(activity_reasons) if activity_reasons else "",
        seconds_since_activity=round(now - last_activity, 3),
    )
    return sample, current_cpu, current_net, now, last_activity


def sample_to_row(sample: Sample) -> list[object]:
    return [
        sample.timestamp,
        sample.elapsed_seconds,
        sample.container_cpu_percent,
        sample.container_cpu_docker_percent,
        sample.container_cpu_limit_cores,
        sample.container_cpu_budget_percent,
        sample.container_mem_usage_mb,
        sample.container_mem_limit_mb,
        sample.container_mem_percent,
        sample.container_net_rx_mb,
        sample.container_net_tx_mb,
        sample.container_net_rx_delta_mb,
        sample.container_net_tx_delta_mb,
        sample.container_block_read_mb,
        sample.container_block_write_mb,
        sample.container_pids,
        sample.system_cpu_percent,
        sample.system_mem_used_mb,
        sample.system_mem_total_mb,
        sample.system_mem_percent,
        "si" if sample.activity_detected else "no",
        sample.activity_reasons,
        sample.seconds_since_activity,
    ]


def headers() -> list[str]:
    return [
        "timestamp",
        "elapsed_seconds",
        "container_cpu_percent",
        "container_cpu_docker_percent",
        "container_cpu_limit_cores",
        "container_cpu_budget_percent",
        "container_mem_usage_mb",
        "container_mem_limit_mb",
        "container_mem_percent",
        "container_net_rx_mb",
        "container_net_tx_mb",
        "container_net_rx_delta_mb",
        "container_net_tx_delta_mb",
        "container_block_read_mb",
        "container_block_write_mb",
        "container_pids",
        "system_cpu_percent",
        "system_mem_used_mb",
        "system_mem_total_mb",
        "system_mem_percent",
        "activity_detected",
        "activity_reasons",
        "seconds_since_activity",
    ]


def write_csv(samples: list[Sample], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(headers())
        for sample in samples:
            writer.writerow(sample_to_row(sample))


def write_xlsx(samples: list[Sample], summary: list[tuple[str, object]], path: Path) -> None:
    sheet_rows = [headers(), *[sample_to_row(sample) for sample in samples]]
    summary_rows = [["metrica", "valor"], *summary]
    files = {
        "[Content_Types].xml": content_types_xml(),
        "_rels/.rels": root_rels_xml(),
        "xl/workbook.xml": workbook_xml(),
        "xl/_rels/workbook.xml.rels": workbook_rels_xml(),
        "xl/worksheets/sheet1.xml": worksheet_xml(sheet_rows),
        "xl/worksheets/sheet2.xml": worksheet_xml(summary_rows),
        "xl/styles.xml": styles_xml(),
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as package:
        for name, content in files.items():
            package.writestr(name, content)


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="muestras" sheetId="1" r:id="rId1"/>
    <sheet name="resumen" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>"""


def workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="1"><fill><patternFill patternType="none"/></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>
</styleSheet>"""


def worksheet_xml(rows: list[list[object]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            ref = f"{column_name(column_index)}{row_index}"
            cells.append(cell_xml(ref, value))
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )


def cell_xml(ref: str, value: object) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = "0" if not math.isfinite(float(value)) else str(round(float(value), 6))
        return f'<c r="{ref}"><v>{number}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def summarize(samples: list[Sample], container: str, started_at: str, finished_at: str) -> list[tuple[str, object]]:
    def values(attribute: str) -> list[float]:
        return [float(getattr(sample, attribute)) for sample in samples]

    def avg(attribute: str) -> float:
        data = values(attribute)
        return round(sum(data) / len(data), 3) if data else 0.0

    def max_value(attribute: str) -> float:
        data = values(attribute)
        return round(max(data), 3) if data else 0.0

    duration = samples[-1].elapsed_seconds if samples else 0
    return [
        ("container", container),
        ("inicio", started_at),
        ("fin", finished_at),
        ("duracion_segundos", round(duration, 3)),
        ("muestras", len(samples)),
        ("container_cpu_promedio_percent", avg("container_cpu_percent")),
        ("container_cpu_max_percent", max_value("container_cpu_percent")),
        ("container_cpu_promedio_docker_percent", avg("container_cpu_docker_percent")),
        ("container_cpu_max_docker_percent", max_value("container_cpu_docker_percent")),
        ("container_cpu_limit_cores", round(samples[-1].container_cpu_limit_cores, 3) if samples else 0),
        ("container_cpu_promedio_cuota_percent", avg("container_cpu_budget_percent")),
        ("container_cpu_max_cuota_percent", max_value("container_cpu_budget_percent")),
        ("container_mem_promedio_mb", avg("container_mem_usage_mb")),
        ("container_mem_max_mb", max_value("container_mem_usage_mb")),
        ("container_mem_max_percent", max_value("container_mem_percent")),
        ("system_cpu_promedio_percent", avg("system_cpu_percent")),
        ("system_cpu_max_percent", max_value("system_cpu_percent")),
        ("system_mem_promedio_percent", avg("system_mem_percent")),
        ("system_mem_max_percent", max_value("system_mem_percent")),
        ("net_rx_final_mb", round(samples[-1].container_net_rx_mb, 3) if samples else 0),
        ("net_tx_final_mb", round(samples[-1].container_net_tx_mb, 3) if samples else 0),
    ]


def write_svg_chart(
    samples: list[Sample],
    path: Path,
    title: str,
    series: list[tuple[str, str, str]],
    y_label: str,
    fixed_max_y: float | None = None,
) -> None:
    width = 1100
    height = 520
    left = 72
    right = 28
    top = 48
    bottom = 64
    plot_width = width - left - right
    plot_height = height - top - bottom
    xs = [sample.elapsed_seconds for sample in samples]
    max_x = max(xs) if xs else 1
    all_values = [
        float(getattr(sample, attribute))
        for attribute, _, _ in series
        for sample in samples
    ]
    if fixed_max_y is not None:
        max_y = max(1.0, fixed_max_y)
    else:
        max_y = max(1.0, (max(all_values) if all_values else 1) * 1.12)

    def point(sample: Sample, attribute: str) -> tuple[float, float]:
        x = left + (sample.elapsed_seconds / max_x) * plot_width if max_x else left
        value = float(getattr(sample, attribute))
        y = top + plot_height - (value / max_y) * plot_height
        return x, y

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Arial,sans-serif;font-size:13px}.title{font-size:20px;font-weight:700}.label{fill:#444}.grid{stroke:#e6e6e6}.axis{stroke:#333}.legend{font-weight:700}</style>",
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        f'<text class="title" x="{left}" y="30">{escape(title)}</text>',
    ]
    for i in range(6):
        y = top + (plot_height / 5) * i
        value = max_y - (max_y / 5) * i
        parts.append(f'<line class="grid" x1="{left}" y1="{y:.2f}" x2="{width-right}" y2="{y:.2f}"/>')
        parts.append(f'<text class="label" x="8" y="{y + 4:.2f}">{value:.1f}</text>')
    parts.append(f'<line class="axis" x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}"/>')
    parts.append(f'<line class="axis" x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}"/>')
    parts.append(f'<text class="label" x="{left}" y="{height-22}">segundos</text>')
    parts.append(f'<text class="label" x="8" y="{top-12}">{escape(y_label)}</text>')

    legend_x = left
    for attribute, label, color in series:
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in (point(sample, attribute) for sample in samples))
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.5" points="{points}"/>')
        parts.append(f'<rect x="{legend_x}" y="{height-45}" width="14" height="14" fill="{color}"/>')
        parts.append(f'<text class="legend" x="{legend_x + 20}" y="{height-33}">{escape(label)}</text>')
        legend_x += 230
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def write_charts(samples: list[Sample], output_dir: Path) -> list[Path]:
    charts = [
        (
            "cpu.svg",
            "CPU: contenedor chatboot normalizado vs sistema",
            [
                ("container_cpu_percent", "chatboot CPU %", "#2563eb"),
                ("system_cpu_percent", "sistema CPU %", "#dc2626"),
            ],
            "%",
        ),
        (
            "cpu_contenedor.svg",
            "CPU: uso del contenedor sobre su cuota",
            [
                ("container_cpu_budget_percent", "chatboot % de cuota", "#0f766e"),
            ],
            "% de cuota",
        ),
        (
            "memoria.svg",
            "Memoria: contenedor chatboot vs sistema",
            [
                ("container_mem_usage_mb", "chatboot MB", "#16a34a"),
                ("system_mem_used_mb", "sistema MB", "#9333ea"),
            ],
            "MB",
        ),
        (
            "memoria_porcentaje.svg",
            "Memoria porcentual",
            [
                ("container_mem_percent", "chatboot %", "#0f766e"),
                ("system_mem_percent", "sistema %", "#ea580c"),
            ],
            "%",
        ),
        (
            "red_contenedor.svg",
            "Red acumulada del contenedor chatboot",
            [
                ("container_net_rx_mb", "RX MB", "#0284c7"),
                ("container_net_tx_mb", "TX MB", "#f59e0b"),
            ],
            "MB",
        ),
    ]
    written: list[Path] = []
    for filename, title, series, y_label in charts:
        path = output_dir / filename
        fixed_max_y = 100.0 if filename == "cpu_contenedor.svg" else None
        write_svg_chart(samples, path, title, series, y_label, fixed_max_y=fixed_max_y)
        written.append(path)
    return written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recolecta metricas del contenedor chatboot y del sistema host.",
    )
    parser.add_argument("--container", default=DEFAULT_CONTAINER, help="Nombre del contenedor Docker.")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS, help="Segundos entre muestras.")
    parser.add_argument("--idle-seconds", type=float, default=DEFAULT_IDLE_SECONDS, help="Segundos sin actividad antes de cerrar.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directorio de salida.")
    parser.add_argument("--no-log-activity", action="store_true", help="No usar docker logs para detectar actividad.")
    parser.add_argument("--no-network-activity", action="store_true", help="No usar red del contenedor para detectar actividad.")
    parser.add_argument("--no-cpu-activity", action="store_true", help="No usar CPU del contenedor para detectar actividad.")
    parser.add_argument("--network-delta-mb", type=float, default=0.001, help="Delta minimo de red para contar actividad.")
    parser.add_argument("--cpu-activity-percent", type=float, default=DEFAULT_CPU_ACTIVITY_PERCENT, help="CPU minima del contenedor para contar actividad.")
    parser.add_argument("--max-seconds", type=float, default=0, help="Duracion maxima opcional. 0 significa sin limite.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        raise RuntimeError("--interval debe ser mayor que 0")
    if args.idle_seconds <= 0:
        raise RuntimeError("--idle-seconds debe ser mayor que 0")
    if not docker_container_exists(args.container):
        raise RuntimeError(
            f"No existe el contenedor {args.container!r}. "
            "Levanta docker compose o pasa --container con el nombre correcto."
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = output_dir / f"rendimiento_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().isoformat(timespec="seconds")
    print(f"Recolectando metricas de {args.container}. Salida: {run_dir}")
    print(f"Se cerrara tras {args.idle_seconds:.0f}s sin actividad. Ctrl+C tambien exporta lo recolectado.")

    samples: list[Sample] = []
    start_time = time.time()
    last_activity = start_time
    last_log_check = start_time
    previous_net: tuple[float, float] | None = None
    previous_cpu = read_cpu_snapshot()
    container_cpu_limit_cores = read_container_cpu_limit_cores(args.container)
    print(f"Cuota de CPU detectada para el contenedor: {container_cpu_limit_cores:.2f} vCPU")

    try:
        while True:
            sample, previous_cpu, previous_net, last_log_check, last_activity = make_sample(
                start_time=start_time,
                container=args.container,
                container_cpu_limit_cores=container_cpu_limit_cores,
                previous_cpu=previous_cpu,
                previous_net=previous_net,
                previous_log_check=last_log_check,
                min_network_delta_mb=args.network_delta_mb,
                cpu_activity_percent=args.cpu_activity_percent,
                detect_logs=not args.no_log_activity,
                detect_network=not args.no_network_activity,
                detect_cpu=not args.no_cpu_activity,
                last_activity=last_activity,
            )
            samples.append(sample)
            print(
                f"[{sample.timestamp}] "
                f"chatboot cpu={sample.container_cpu_percent:.2f}% "
                f"(docker={sample.container_cpu_docker_percent:.2f}%) "
                f"cuota={sample.container_cpu_budget_percent:.2f}% "
                f"mem={sample.container_mem_usage_mb:.1f}MB "
                f"sistema cpu={sample.system_cpu_percent:.2f}% "
                f"ram={sample.system_mem_percent:.1f}% "
                f"actividad={sample.activity_reasons or '-'} "
                f"inactivo={sample.seconds_since_activity:.0f}s"
            )
            if sample.seconds_since_activity >= args.idle_seconds:
                print("Tiempo de inactividad alcanzado; generando reporte.")
                break
            if args.max_seconds and sample.elapsed_seconds >= args.max_seconds:
                print("Duracion maxima alcanzada; generando reporte.")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nInterrumpido por usuario; generando reporte parcial.")

    if not samples:
        print("No se recolectaron muestras.")
        return 1

    finished_at = datetime.now().isoformat(timespec="seconds")
    summary = summarize(samples, args.container, started_at, finished_at)
    csv_path = run_dir / "metricas.csv"
    xlsx_path = run_dir / "metricas.xlsx"
    write_csv(samples, csv_path)
    write_xlsx(samples, summary, xlsx_path)
    chart_paths = write_charts(samples, run_dir)

    print("\nReporte generado:")
    print(f"- Excel: {xlsx_path}")
    print(f"- CSV:   {csv_path}")
    for chart_path in chart_paths:
        print(f"- Grafico: {chart_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
