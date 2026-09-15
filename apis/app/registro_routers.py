from fastapi import FastAPI

from rutas.autenticacion.autentificar import router as auth_router
from rutas.panel_administrativo.atractivos import router as atractivos_router
from rutas.panel_administrativo.contenido_chatbots import router as contenido_chatbots_router
from rutas.panel_administrativo.cuentas_admin import (
    router_cargos,
    router_cuentas,
    router_permisos,
)
from rutas.panel_administrativo.dashboard import router as dashboard_router
from rutas.panel_administrativo.noticias import router as noticias_router
from rutas.panel_administrativo.registro_acciones import router as registro_acciones_router
from rutas.panel_administrativo.rutas_turisticas import router as rutas_turisticas_router
from rutas.historial_usuario import router as historial_usuario_router
from rutas.favoritos_user import router as favoritos_router
from rutas.noticias_usuario import router as noticias_usuario_router
from rutas.rutas_buses import router as rutas_buses_router
from rutas.rutas_movil_turismo import router as rutas_movil_turismo_router
from rutas.sitio_ficha import router as ficha_sitio_router
from rutas.sitio_turismo import router as sitios_router
from rutas.chatboot_exploracion.atributos_booleanos_consulta import (
    router as atributos_booleanos_consulta_router,
)
from rutas.chatboot_exploracion.busqueda_referencia import router as busqueda_referencia_router
from rutas.chatboot_exploracion.busqueda_ubicacion import router as busqueda_ubicacion_router
from rutas.chatboot_exploracion.busqueda_semantica_consulta import (
    router as busqueda_semantica_consulta_router,
)
from rutas.chatboot_exploracion.contacto_busqueda import router as contacto_busqueda_router
from rutas.chatboot_exploracion.gis_consulta import router as gis_consulta_router
from rutas.chatboot_exploracion.fallback_opciones import router as fallback_opciones_router
from rutas.chatboot_exploracion.historial_exploracion import (
    router as historial_exploracion_router,
)
from rutas.chatboot_exploracion.horario_consulta import router as horario_consulta_router
from rutas.chatboot_exploracion.precio_consulta import router as precio_consulta_router
from rutas.chatboot_exploracion.ruta_consulta import router as ruta_consulta_router
from rutas.chatboot_exploracion.tarifa_acceso_consulta import (
    router as tarifa_acceso_consulta_router,
)
from rutas.chatboot_especifico.chatboot_pregunta_directa import (
    router as chatboot_pregunta_directa_router,
)
from rutas.chatboot_especifico.historial_pregunta_directa import (
    router as historial_pregunta_directa_router,
)
from rutas.chatboot_especifico.pregunta_directa import router as pregunta_directa_router
from rutas.compartido.comprobar_archivos import router as comprobar_archivos_router


def registrar_routers(app: FastAPI) -> None:
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(atractivos_router, prefix="/api/v1")
    app.include_router(rutas_turisticas_router, prefix="/api/v1")
    app.include_router(noticias_router, prefix="/api/v1")
    app.include_router(noticias_usuario_router, prefix="/api/v1")
    app.include_router(registro_acciones_router, prefix="/api/v1")
    app.include_router(rutas_movil_turismo_router, prefix="/api/v1")
    app.include_router(contenido_chatbots_router, prefix="/api/v1")
    app.include_router(router_cuentas, prefix="/api/v1")
    app.include_router(router_cargos, prefix="/api/v1")
    app.include_router(router_permisos, prefix="/api/v1")
    app.include_router(sitios_router, prefix="/api/v1")
    app.include_router(ficha_sitio_router, prefix="/api/v1")
    app.include_router(favoritos_router, prefix="/api/v1")
    app.include_router(comprobar_archivos_router, prefix="/api/v1")
    app.include_router(rutas_buses_router, prefix="/api/v1")
    app.include_router(busqueda_ubicacion_router, prefix="/api/v1")
    app.include_router(busqueda_referencia_router, prefix="/api/v1")
    app.include_router(contacto_busqueda_router, prefix="/api/v1")
    app.include_router(horario_consulta_router, prefix="/api/v1")
    app.include_router(precio_consulta_router, prefix="/api/v1")
    app.include_router(tarifa_acceso_consulta_router, prefix="/api/v1")
    app.include_router(atributos_booleanos_consulta_router, prefix="/api/v1")
    app.include_router(gis_consulta_router, prefix="/api/v1")
    app.include_router(ruta_consulta_router, prefix="/api/v1")
    app.include_router(busqueda_semantica_consulta_router, prefix="/api/v1")
    app.include_router(pregunta_directa_router, prefix="/api/v1")
    app.include_router(fallback_opciones_router, prefix="/api/v1")
    app.include_router(historial_exploracion_router, prefix="/api/v1")
    app.include_router(historial_pregunta_directa_router, prefix="/api/v1")
    app.include_router(chatboot_pregunta_directa_router, prefix="/api/v1")
    app.include_router(historial_usuario_router, prefix="/api/v1")
