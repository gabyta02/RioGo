"""Prueba integración: búsqueda semántica montar a caballo."""
import json
import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from esquemas.chatboot_exploracion.busqueda_semantica_consulta import BusquedaSemanticaConsultaEntrada
from servicios.chatboot_exploracion.busqueda_semantica_consulta import consultar_sitios_por_busqueda_semantica


def _db_session():
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URL")
    if not db_url:
        from core.config import settings

        db_url = settings.DATABASE_URL
    engine = create_engine(db_url)
    return sessionmaker(bind=engine)()


def _print_result(label: str, result) -> None:
    data = result.model_dump(mode="json")
    print(f"\n=== {label} ===")
    print("tipo:", type(result).__name__)
    print("ids_sitio:", data.get("ids_sitio"))
    retro = data.get("retroalimentacion") or data.get("sin_sitios")
    print("retro:", json.dumps(retro, ensure_ascii=False))
    for c in (data.get("candidatos") or [])[:10]:
        print(
            f"  id={c['id_sitio']} {c['nombre'][:35]:35} "
            f"score={c['score_final']:.4f} boost={c['boost_keywords']} "
            f"kw={c['keywords_match']} supera={c['supera_umbral']}"
        )


def main() -> int:
    db = _db_session()
    ids_cat = [31, 32, 51, 52, 53, 54, 55, 56, 57]
    payload = BusquedaSemanticaConsultaEntrada(
        ids_consulta=ids_cat,
        texto_embeddings="montar a caballo",
        keywords=["montar a caballo", "paseos a caballo"],
        excluir_terminos=[],
    )
    result = consultar_sitios_por_busqueda_semantica(db, payload)
    _print_result("LOCAL (categorías)", result)

    data = result.model_dump(mode="json")
    for c in data.get("candidatos") or []:
        if c["id_sitio"] == 53:
            print("\nChimborazo Tours (53) local:", json.dumps(c, ensure_ascii=False, indent=2))
            break

    if 53 in (data.get("ids_sitio") or []):
        print("\nOK: Chimborazo Tours (53) en ids_sitio con filtro categorías")
        db.close()
        return 0

    # Si no pasó umbral local, el servicio debería haber hecho fallback global
    if not data.get("ids_sitio"):
        print("\nSin ids en alcance local — verificar fallback global vía API completa")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
