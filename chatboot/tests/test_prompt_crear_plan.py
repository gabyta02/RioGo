from application.nodes.chatboot_exploracion.utilidades.crear_plan_tools import (
    cargar_prompt_crear_plan,
)


def test_prompt_fallback_se_define_por_intencion_no_por_mensaje_completo():
    prompt = cargar_prompt_crear_plan()

    assert "Fallback solo para una intención que no se puede ejecutar" in prompt
    assert "Regla de no mezcla por intención" in prompt
    assert "dentro del mismo bloque `ejecucion_herramienta`" in prompt
    assert "segunda intención independiente" in prompt


def test_prompt_ejemplos_evitan_fallback_en_cabalgata_y_hotel_lugar_bonito():
    prompt = cargar_prompt_crear_plan()

    assert '"dónde puedo montar a caballo" → una sola consulta: `busqueda_semantica`. NO fallback' in prompt
    assert '"quiero un hotel barato y un lugar bonito" → `busqueda_semantica`("hotel") + `precio`, y otra consulta con `fallback` para "un lugar bonito".' in prompt
    assert '"quiero un hotel barato y algo para hacer"' in prompt
    assert '"quiero hablar con un guía turístico" → `busqueda_semantica`' in prompt
    assert '"entrada gratuita" o "acceso gratis" si no hay condición de público específica; usa `atributos_booleanos.es_gratuito:true`' in prompt
    assert '"mañana" como día siguiente, sin hora ni bloque del día → `tipo:"dias_solamente"`' in prompt
    assert '"cuál de estos hoteles es mejor" → `fallback`' in prompt


def test_prompt_usa_correcciones_y_no_inventa_terminos_raros():
    prompt = cargar_prompt_crear_plan()

    assert "correcciones_detectadas" in prompt
    assert 'usa el término `corregido`' in prompt
    assert "No inventes significados, variantes ni sinónimos" in prompt
    assert "usa `fallback` para pedir retroalimentación/aclaración" in prompt
