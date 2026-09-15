#!/usr/bin/env python3
"""Prueba directa de concurrencia contra DeepSeek, sin backend interno.

Ejecutar dentro del contenedor chatboot:

    python tests/test_deepseek_directo.py --concurrency 100 --requests 100

La prueba carga preguntas desde tests/preguntas.json y llama al proveedor LLM
directamente con AsyncOpenAI. No usa WebSocket, LangGraph, PostgreSQL ni apis.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, RateLimitError


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS_FILE = BASE_DIR / "tests" / "preguntas.json"
DEFAULT_OUTPUT_DIR = BASE_DIR / "tests" / "resultados_deepseek_directo"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from infrastructure.config import get_settings


@dataclass
class ResultadoRequest:
    index: int
    pregunta_id: str
    nivel: str
    ok: bool
    status_code: int | None
    error_type: str | None
    error: str | None
    duration_seconds: float
    response_chars: int


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


def _load_questions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list) or not data:
        raise ValueError(f"No hay preguntas validas en {path}")
    questions: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pregunta = str(item.get("pregunta") or "").strip()
        if pregunta:
            questions.append(item)
    if not questions:
        raise ValueError(f"No se encontraron preguntas con texto en {path}")
    return questions


def _build_prompt(question: str, json_response: bool) -> str:
    if json_response:
        return (
            "Responde exclusivamente con JSON valido. "
            "Usa el formato {\"respuesta\":\"...\"}. "
            f"Pregunta del usuario: {question}"
        )
    return (
        "Eres un asistente turistico de Riobamba. "
        "Responde breve, en una sola frase. "
        f"Pregunta del usuario: {question}"
    )


async def _call_llm(
    *,
    client: AsyncOpenAI,
    model: str,
    question: dict[str, Any],
    index: int,
    json_response: bool,
    max_tokens: int,
) -> ResultadoRequest:
    started = time.perf_counter()
    pregunta = str(question.get("pregunta") or "")
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": _build_prompt(pregunta, json_response)}],
        "max_tokens": max_tokens,
        "stream": False,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    if json_response:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await client.chat.completions.create(**kwargs)
        content = getattr(response.choices[0].message, "content", None) or ""
        duration = time.perf_counter() - started
        return ResultadoRequest(
            index=index,
            pregunta_id=str(question.get("id") or index),
            nivel=str(question.get("nivel") or ""),
            ok=True,
            status_code=None,
            error_type=None,
            error=None,
            duration_seconds=round(duration, 3),
            response_chars=len(content),
        )
    except Exception as exc:
        duration = time.perf_counter() - started
        return ResultadoRequest(
            index=index,
            pregunta_id=str(question.get("id") or index),
            nivel=str(question.get("nivel") or ""),
            ok=False,
            status_code=getattr(exc, "status_code", None),
            error_type=type(exc).__name__,
            error=str(exc),
            duration_seconds=round(duration, 3),
            response_chars=0,
        )


async def _run(args: argparse.Namespace) -> tuple[dict[str, Any], list[ResultadoRequest]]:
    load_dotenv(BASE_DIR / ".env")
    settings = get_settings()
    provider_name = args.provider
    provider = settings.llm.providers[provider_name]
    api_key = os.getenv(provider.api_key_env)
    if not api_key:
        raise RuntimeError(
            f"Falta API key. Define {provider.api_key_env} en el entorno o .env"
        )

    questions = _load_questions(Path(args.questions_file))
    requests_count = args.requests or len(questions)
    selected = [questions[index % len(questions)] for index in range(requests_count)]
    max_tokens = args.max_tokens or min(provider.max_tokens or 512, 512)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=provider.base_url,
        timeout=args.timeout or provider.timeout_seconds,
        max_retries=0,
    )

    semaphore = asyncio.Semaphore(args.concurrency)
    started = time.perf_counter()

    async def worker(index: int, question: dict[str, Any]) -> ResultadoRequest:
        async with semaphore:
            return await _call_llm(
                client=client,
                model=args.model or provider.model,
                question=question,
                index=index,
                json_response=args.json_response,
                max_tokens=max_tokens,
            )

    tasks = [worker(index, question) for index, question in enumerate(selected, start=1)]
    results = await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - started

    ok_durations = [item.duration_seconds for item in results if item.ok]
    all_durations = [item.duration_seconds for item in results]
    errors: dict[str, int] = {}
    status_codes: dict[str, int] = {}
    for item in results:
        if item.ok:
            continue
        errors[item.error_type or "UnknownError"] = errors.get(item.error_type or "UnknownError", 0) + 1
        status_key = str(item.status_code)
        status_codes[status_key] = status_codes.get(status_key, 0) + 1

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "provider": provider_name,
        "model": args.model or provider.model,
        "base_url": provider.base_url,
        "requests": len(results),
        "concurrency": args.concurrency,
        "timeout_seconds": args.timeout or provider.timeout_seconds,
        "max_tokens": max_tokens,
        "json_response": args.json_response,
        "total_duration_seconds": round(total_duration, 3),
        "ok": sum(1 for item in results if item.ok),
        "failed": sum(1 for item in results if not item.ok),
        "success_rate_percent": round(100 * sum(1 for item in results if item.ok) / len(results), 2),
        "errors_by_type": errors,
        "errors_by_status_code": status_codes,
        "latency_all_seconds": {
            "min": round(min(all_durations), 3) if all_durations else 0,
            "avg": round(statistics.mean(all_durations), 3) if all_durations else 0,
            "p50": round(_percentile(all_durations, 0.50), 3),
            "p95": round(_percentile(all_durations, 0.95), 3),
            "p99": round(_percentile(all_durations, 0.99), 3),
            "max": round(max(all_durations), 3) if all_durations else 0,
        },
        "latency_ok_seconds": {
            "min": round(min(ok_durations), 3) if ok_durations else 0,
            "avg": round(statistics.mean(ok_durations), 3) if ok_durations else 0,
            "p50": round(_percentile(ok_durations, 0.50), 3),
            "p95": round(_percentile(ok_durations, 0.95), 3),
            "p99": round(_percentile(ok_durations, 0.99), 3),
            "max": round(max(ok_durations), 3) if ok_durations else 0,
        },
    }
    return summary, results


def _write_outputs(
    output_dir: Path,
    summary: dict[str, Any],
    results: list[ResultadoRequest],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = output_dir / f"deepseek_directo_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir()

    with (run_dir / "resumen.json").open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    with (run_dir / "resultados.jsonl").open("w", encoding="utf-8") as file:
        for item in results:
            file.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")

    with (run_dir / "resultados.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for item in results:
            writer.writerow(asdict(item))

    summary["output_dir"] = str(run_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prueba directa de DeepSeek con concurrencia controlada."
    )
    parser.add_argument("--questions-file", default=str(DEFAULT_QUESTIONS_FILE))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--provider", default="deepseek")
    parser.add_argument("--model", default=None)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--json-response", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.requests < 1:
        raise SystemExit("--requests debe ser mayor a 0")
    if args.concurrency < 1:
        raise SystemExit("--concurrency debe ser mayor a 0")

    summary, results = asyncio.run(_run(args))
    _write_outputs(Path(args.output_dir), summary, results)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
