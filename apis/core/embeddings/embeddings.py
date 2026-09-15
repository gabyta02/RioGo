import os
from pathlib import Path
from typing import Literal

import requests
from dotenv import load_dotenv
from fastapi import HTTPException, status

from core.embeddings.cache_embedding import (
    guardar_embedding_cache,
    leer_embedding_cache,
)
from core.infra.texto_limpieza import limpiar_texto_para_embedding

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / "panel_admin" / ".env", override=False)

VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"
EMBEDDING_DIMENSION = 1024
InputTypeEmbedding = Literal["query", "document"]


def _cache_habilitado() -> bool:
    return os.getenv("EMBEDDING_CACHE_DISABLED", "").lower() not in {"1", "true", "yes"}


def _config_voyage() -> tuple[str, str]:
    api_key = os.getenv("VOYAGE_API_KEY")
    modelo = os.getenv("MODELO_VOYAGE", "voyage-4-lite")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VOYAGE_API_KEY no esta configurada para generar embeddings",
        )
    return api_key, modelo


def _vector_a_literal(vector: list[float]) -> str:
    if len(vector) != EMBEDDING_DIMENSION:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"El proveedor de embeddings devolvio {len(vector)} dimensiones y se esperaban "
                f"{EMBEDDING_DIMENSION}."
            ),
        )
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def _solicitar_embeddings_voyage(
    textos: list[str],
    *,
    input_type: InputTypeEmbedding,
    api_key: str,
    modelo: str,
) -> list[list[float]]:
    try:
        response = requests.post(
            VOYAGE_EMBEDDINGS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "input": textos,
                "model": modelo,
                "input_type": input_type,
                "truncation": True,
                "output_dimension": EMBEDDING_DIMENSION,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        items = sorted(data["data"], key=lambda item: int(item["index"]))
        return [item["embedding"] for item in items]
    except (requests.RequestException, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo generar el embedding con Voyage",
        ) from exc


def generar_embeddings(
    textos: list[str],
    *,
    input_type: InputTypeEmbedding = "document",
) -> list[str | None]:
    if not textos:
        return []

    api_key, modelo = _config_voyage()
    usar_cache = _cache_habilitado()
    resultados: list[str | None] = [None] * len(textos)
    pendientes: list[tuple[int, str]] = []

    for indice, texto in enumerate(textos):
        contenido = limpiar_texto_para_embedding(texto)
        if not contenido:
            continue
        if usar_cache:
            cacheado = leer_embedding_cache(contenido, input_type, modelo)
            if cacheado:
                resultados[indice] = cacheado
                continue
        pendientes.append((indice, contenido))

    if not pendientes:
        return resultados

    vectores = _solicitar_embeddings_voyage(
        [contenido for _, contenido in pendientes],
        input_type=input_type,
        api_key=api_key,
        modelo=modelo,
    )

    if len(vectores) != len(pendientes):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El proveedor de embeddings devolvio una cantidad inesperada de vectores",
        )

    for (indice, contenido), vector in zip(pendientes, vectores):
        embedding = _vector_a_literal(vector)
        resultados[indice] = embedding
        if usar_cache:
            guardar_embedding_cache(contenido, input_type, modelo, embedding)

    return resultados


def generar_embedding(
    texto: str | None,
    *,
    input_type: InputTypeEmbedding = "document",
) -> str | None:
    if texto is None:
        return None
    resultados = generar_embeddings([texto], input_type=input_type)
    return resultados[0] if resultados else None
