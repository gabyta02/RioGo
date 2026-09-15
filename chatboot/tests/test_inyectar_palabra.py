from application.nodes.chatboot_exploracion.utilidades.crear_plan_tools import (
    construir_payload_clasificacion,
)
from application.shared.inyectar_palabra import extraer_palabras_inyectadas


def test_inyectar_palabra_corrige_typo_salchipapa_con_confianza():
    palabras = extraer_palabras_inyectadas("quiero comer una slachipapa")

    assert palabras
    salchipapa = palabras[0]
    assert salchipapa["palabra"] == "salchipapa"
    assert salchipapa["termino_normalizado"] == "salchipapa"
    assert salchipapa["texto_detectado"] == "slachipapa"
    assert salchipapa["correccion_sugerida"] is True
    assert salchipapa["score"] >= 90


def test_payload_planificador_incluye_correcciones_detectadas():
    palabras = extraer_palabras_inyectadas("quiero comer una slachipapa")

    payload = construir_payload_clasificacion(
        {
            "texto_usuario": "quiero comer una slachipapa",
            "score_prompt_inyection": 0,
            "palabras_inyectadas": palabras,
        }
    )

    assert payload["correcciones_detectadas"] == [
        {
            "original": "slachipapa",
            "corregido": "salchipapa",
            "confianza": "media",
            "score": 90,
            "significado": "comida_tradicional",
        }
    ]
    assert isinstance(payload["palabras_inyectadas"][0], dict)
