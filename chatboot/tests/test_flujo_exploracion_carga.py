#!/usr/bin/env python3
"""Carga rastreada del flujo de exploracion.

Ejecuta preguntas aleatorias durante una ventana de tiempo y mide cada etapa:
shared_flow, cargar_memoria, crear_plan, ejecutar_plan, guardar_memoria y total.

Ejemplo dentro del contenedor chatboot:

    python tests/test_flujo_exploracion_carga.py --concurrency 50 --duration-seconds 120
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS_FILE = BASE_DIR / "tests" / "preguntas.json"
DEFAULT_OUTPUT_DIR = BASE_DIR / "tests" / "resultados_flujo_exploracion"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from application.nodes.chatboot_exploracion.utilidades.cargar_memoria import (
    cargar_memoria_exploracion,
)
from application.nodes.chatboot_exploracion.utilidades.crear_plan_tools import (
    crear_plan_exploracion,
)
from application.nodes.chatboot_exploracion.utilidades.ejecutar_plan_tools import (
    ejecutar_plan_exploracion,
)
from application.nodes.chatboot_exploracion.utilidades.guardar_memoria import (
    guardar_memoria_exploracion,
)
from application.orquestador import (
    _construir_estado_inicial,
    validar_peticion_websocket,
)
from application.shared.flow import ejecutar_shared_flow


@dataclass
class ResultadoFlujo:
    index: int
    pregunta_id: str
    nivel: str
    pregunta: str
    ok: bool
    punto_quiebre: str | None
    error_type: str | None
    error: str | None
    plan_valido: bool
    errores_formato: str
    herramientas: str
    total_seconds: float
    stage_seconds: dict[str, float] = field(default_factory=dict)


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "min": round(min(values), 3) if values else 0,
        "avg": round(statistics.mean(values), 3) if values else 0,
        "p50": round(_percentile(values, 0.50), 3),
        "p95": round(_percentile(values, 0.95), 3),
        "p99": round(_percentile(values, 0.99), 3),
        "max": round(max(values), 3) if values else 0,
    }


def _load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    questions = [
        item
        for item in data
        if isinstance(item, dict) and str(item.get("pregunta") or "").strip()
    ]
    if not questions:
        raise ValueError(f"No hay preguntas validas en {path}")
    return questions


def _payload(question: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "pregunta_chatboot": "exploracion",
        "mensaje": {
            "mensaje_usuario": str(question["pregunta"]),
            "client_message_id": f"stress-{index}-{uuid4()}",
            "id_usuario": None,
            "sesion_Id": f"stress-session-{uuid4()}",
            "ubicacion_usuario": {
                "latitud": -1.6635,
                "longitud": -78.6546,
            },
        },
    }


def _serializar_error_list(value: Any) -> str:
    if not value:
        return ""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))[:1000]


def _extraer_herramientas(state: dict[str, Any]) -> str:
    resultado = state.get("resultado_exploracion")
    if not isinstance(resultado, dict):
        return ""
    herramientas = resultado.get("herramientas_plan") or resultado.get("herramientas")
    if not herramientas:
        plan = resultado.get("plan")
        if isinstance(plan, dict):
            herramientas = [
                consulta.get("herramienta")
                for consulta in plan.get("consultas") or []
                if isinstance(consulta, dict)
            ]
    return json.dumps(herramientas or [], ensure_ascii=False, separators=(",", ":"))[:1000]


async def _run_one(index: int, question: dict[str, Any], timeout: float) -> ResultadoFlujo:
    started_total = time.perf_counter()
    stage_seconds: dict[str, float] = {}
    pregunta = str(question.get("pregunta") or "")

    async def timed(stage: str, func: Any, *args: Any) -> Any:
        started = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args)
            return await asyncio.to_thread(func, *args)
        finally:
            stage_seconds[stage] = round(time.perf_counter() - started, 3)

    async def execute() -> ResultadoFlujo:
        paquete = validar_peticion_websocket(_payload(question, index))
        estado_shared = await timed(
            "shared_flow",
            ejecutar_shared_flow,
            _construir_estado_inicial(paquete),
        )
        clasificacion_final = estado_shared.get("clasificacion_final")
        if not clasificacion_final:
            raise RuntimeError("shared_flow no genero clasificacion_final")
        if estado_shared.get("bloqueado"):
            return ResultadoFlujo(
                index=index,
                pregunta_id=str(question.get("id") or index),
                nivel=str(question.get("nivel") or ""),
                pregunta=pregunta,
                ok=False,
                punto_quiebre="shared_flow_bloqueado",
                error_type=None,
                error=str(estado_shared.get("motivo_bloqueo") or "bloqueado"),
                plan_valido=False,
                errores_formato="",
                herramientas="",
                total_seconds=round(time.perf_counter() - started_total, 3),
                stage_seconds=stage_seconds,
            )

        state: dict[str, Any] = {
            "sesion_id": clasificacion_final["sesion_id"],
            "client_message_id": clasificacion_final["client_message_id"],
            "ubicacion_usuario": clasificacion_final["ubicacion_usuario"],
            "texto_usuario": clasificacion_final["mensaje"]["texto_limpio"],
            "score_prompt_inyection": clasificacion_final["mensaje"][
                "riesgo_prompt_inyection"
            ]["score"],
            "palabras_inyectadas": [
                f"{item['palabra']}:{item['significado']}"
                for item in clasificacion_final["mensaje"]["palabras_inyectadas"]
                if item.get("palabra") and item.get("significado")
            ],
            "memoria": {"turnos": []},
            "prompt_clasificacion": "",
            "respuesta_llm_cruda": "",
            "plan": None,
            "plan_valido": False,
            "errores_formato": [],
            "mensaje_sistema": None,
            "mensaje_app": None,
            "resultado_exploracion": None,
        }

        state = await timed("cargar_memoria", cargar_memoria_exploracion, state)
        state = await timed("crear_plan", crear_plan_exploracion, state)

        errores_formato = state.get("errores_formato") or []
        plan_valido = bool(state.get("plan_valido"))
        if not plan_valido:
            return ResultadoFlujo(
                index=index,
                pregunta_id=str(question.get("id") or index),
                nivel=str(question.get("nivel") or ""),
                pregunta=pregunta,
                ok=False,
                punto_quiebre="crear_plan",
                error_type=None,
                error=_serializar_error_list(errores_formato),
                plan_valido=False,
                errores_formato=_serializar_error_list(errores_formato),
                herramientas="",
                total_seconds=round(time.perf_counter() - started_total, 3),
                stage_seconds=stage_seconds,
            )

        state = await timed("ejecutar_plan", ejecutar_plan_exploracion, state)
        state = await timed("guardar_memoria", guardar_memoria_exploracion, state)

        resultado = state.get("resultado_exploracion")
        ok = isinstance(resultado, dict) and bool(resultado.get("plan_valido", plan_valido))
        return ResultadoFlujo(
            index=index,
            pregunta_id=str(question.get("id") or index),
            nivel=str(question.get("nivel") or ""),
            pregunta=pregunta,
            ok=ok,
            punto_quiebre=None if ok else "ejecutar_plan",
            error_type=None,
            error=None if ok else _serializar_error_list(state.get("errores_formato")),
            plan_valido=plan_valido,
            errores_formato=_serializar_error_list(state.get("errores_formato")),
            herramientas=_extraer_herramientas(state),
            total_seconds=round(time.perf_counter() - started_total, 3),
            stage_seconds=stage_seconds,
        )

    try:
        return await asyncio.wait_for(execute(), timeout=timeout)
    except asyncio.TimeoutError:
        return ResultadoFlujo(
            index=index,
            pregunta_id=str(question.get("id") or index),
            nivel=str(question.get("nivel") or ""),
            pregunta=pregunta,
            ok=False,
            punto_quiebre="timeout",
            error_type="TimeoutError",
            error=f"timeout_{timeout:.0f}s",
            plan_valido=False,
            errores_formato="",
            herramientas="",
            total_seconds=round(time.perf_counter() - started_total, 3),
            stage_seconds=stage_seconds,
        )
    except Exception as exc:
        last_stage = "inicio"
        if stage_seconds:
            last_stage = list(stage_seconds)[-1]
        return ResultadoFlujo(
            index=index,
            pregunta_id=str(question.get("id") or index),
            nivel=str(question.get("nivel") or ""),
            pregunta=pregunta,
            ok=False,
            punto_quiebre=last_stage,
            error_type=type(exc).__name__,
            error=str(exc),
            plan_valido=False,
            errores_formato="",
            herramientas="",
            total_seconds=round(time.perf_counter() - started_total, 3),
            stage_seconds=stage_seconds,
        )


async def _run(args: argparse.Namespace) -> tuple[dict[str, Any], list[ResultadoFlujo]]:
    questions = _load_questions(Path(args.questions_file))
    random.seed(args.seed)
    end_at = time.monotonic() + args.duration_seconds
    semaphore = asyncio.Semaphore(args.concurrency)
    results: list[ResultadoFlujo] = []
    pending: set[asyncio.Task[ResultadoFlujo]] = set()
    next_index = 1
    started = time.perf_counter()

    async def launch_one(index: int) -> ResultadoFlujo:
        question = random.choice(questions)
        async with semaphore:
            return await _run_one(index, question, args.request_timeout_seconds)

    while time.monotonic() < end_at:
        while len(pending) < args.concurrency and time.monotonic() < end_at:
            pending.add(asyncio.create_task(launch_one(next_index)))
            next_index += 1
        if not pending:
            await asyncio.sleep(0.01)
            continue
        done, pending = await asyncio.wait(
            pending,
            timeout=0.25,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            results.append(task.result())

    if pending:
        done, _ = await asyncio.wait(pending)
        for task in done:
            results.append(task.result())

    total_duration = time.perf_counter() - started
    ok_count = sum(1 for item in results if item.ok)
    failed_count = len(results) - ok_count

    breakpoints: dict[str, int] = {}
    errors: dict[str, int] = {}
    for item in results:
        if item.ok:
            continue
        breakpoints[item.punto_quiebre or "desconocido"] = (
            breakpoints.get(item.punto_quiebre or "desconocido", 0) + 1
        )
        errors[item.error_type or item.error or "sin_tipo"] = (
            errors.get(item.error_type or item.error or "sin_tipo", 0) + 1
        )

    stage_names = sorted({stage for item in results for stage in item.stage_seconds})
    stage_stats = {
        stage: _stats(
            [
                item.stage_seconds[stage]
                for item in results
                if stage in item.stage_seconds
            ]
        )
        for stage in stage_names
    }

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "questions_file": str(args.questions_file),
        "concurrency": args.concurrency,
        "duration_seconds": args.duration_seconds,
        "request_timeout_seconds": args.request_timeout_seconds,
        "total_duration_seconds": round(total_duration, 3),
        "requests_completed": len(results),
        "throughput_rps": round(len(results) / total_duration, 3) if total_duration else 0,
        "ok": ok_count,
        "failed": failed_count,
        "success_rate_percent": round(100 * ok_count / len(results), 2) if results else 0,
        "breakpoints": breakpoints,
        "errors": errors,
        "latency_total_seconds": _stats([item.total_seconds for item in results]),
        "stage_latency_seconds": stage_stats,
        "slowest": [
            {
                "index": item.index,
                "pregunta_id": item.pregunta_id,
                "ok": item.ok,
                "punto_quiebre": item.punto_quiebre,
                "total_seconds": item.total_seconds,
                "stage_seconds": item.stage_seconds,
                "error_type": item.error_type,
                "error": item.error,
            }
            for item in sorted(results, key=lambda value: value.total_seconds, reverse=True)[:10]
        ],
    }
    return summary, results


def _write_outputs(
    output_dir: Path,
    summary: dict[str, Any],
    results: list[ResultadoFlujo],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / f"flujo_exploracion_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir()

    summary["output_dir"] = str(run_dir)
    with (run_dir / "resumen.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    with (run_dir / "resultados.jsonl").open("w", encoding="utf-8") as file:
        for item in results:
            file.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    fieldnames = [
        "index",
        "pregunta_id",
        "nivel",
        "pregunta",
        "ok",
        "punto_quiebre",
        "error_type",
        "error",
        "plan_valido",
        "errores_formato",
        "herramientas",
        "total_seconds",
        "stage_seconds",
    ]
    with (run_dir / "resultados.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in results:
            row = asdict(item)
            row["stage_seconds"] = json.dumps(
                item.stage_seconds,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            writer.writerow(row)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Carga de exploracion con rastreo por etapa."
    )
    parser.add_argument("--questions-file", default=str(DEFAULT_QUESTIONS_FILE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--duration-seconds", type=float, default=120)
    parser.add_argument("--request-timeout-seconds", type=float, default=60)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.concurrency < 1:
        raise SystemExit("--concurrency debe ser mayor a 0")
    if args.duration_seconds <= 0:
        raise SystemExit("--duration-seconds debe ser mayor a 0")
    summary, results = asyncio.run(_run(args))
    _write_outputs(Path(args.output_dir), summary, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
