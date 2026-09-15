from sqlalchemy.orm import Session, joinedload, selectinload

from core.imagenes import normalizar_url_imagen
from modelos.sitios_turismo import Horario, Sitio


def opciones_sitio_detalle():
    return (
        joinedload(Sitio.categoria),
        joinedload(Sitio.subcategoria),
        joinedload(Sitio.direccion),
        joinedload(Sitio.horario).selectinload(Horario.detalles),
        joinedload(Sitio.precio),
        selectinload(Sitio.media),
        selectinload(Sitio.tarifas),
    )


def obtener_sitio_por_id(db: Session, id_sitio: int):
    sitio = (
        db.query(Sitio)
        .options(*opciones_sitio_detalle())
        .filter(Sitio.id_sitio == id_sitio)
        .first()
    )

    if not sitio:
        return None

    return transformar_sitio_para_app(sitio)


def construir_horario_resumen(horario) -> str:
    if not horario:
        return "No disponible"

    if horario.abierto_24h:
        return "Abierto 24 horas"

    if horario.comentario:
        return horario.comentario

    if horario.detalles:
        dias = {
            1: "Lunes",
            2: "Martes",
            3: "Miércoles",
            4: "Jueves",
            5: "Viernes",
            6: "Sábado",
            7: "Domingo",
        }

        detalles_ordenados = sorted(horario.detalles, key=lambda x: x.dia_semana)

        resumen = []
        for detalle in detalles_ordenados:
            if detalle.hora_inicio and detalle.hora_fin:
                dia = dias.get(detalle.dia_semana, f"Día {detalle.dia_semana}")
                hora_inicio = detalle.hora_inicio.strftime("%H:%M")
                hora_fin = detalle.hora_fin.strftime("%H:%M")
                resumen.append(f"{dia}: {hora_inicio} - {hora_fin}")

        if resumen:
            return " | ".join(resumen)

    return "No disponible"


from core.chatboot_evaluacion.precio_compacto import construir_texto_precio_resumen


def construir_entrada_resumen(sitio) -> str:
    return construir_texto_precio_resumen(sitio)


def construir_accesibilidad_resumen(sitio) -> str:
    if not sitio.accesibilidad:
        return "No disponible"

    valor = str(sitio.accesibilidad)

    if "." in valor:
        valor = valor.split(".")[-1]

    textos = {
        "nula": "Sin accesibilidad registrada",
        "parcial": "Accesibilidad parcial",
        "completa": "Accesibilidad completa",
    }

    return textos.get(valor, valor)


def construir_direccion(sitio) -> str:
    if sitio.direccion and sitio.direccion.direccion_texto:
        return sitio.direccion.direccion_texto

    if sitio.direccion and sitio.direccion.referencia_adicional:
        return sitio.direccion.referencia_adicional

    return "Dirección no disponible"


def construir_tarifas(sitio):
    tarifas = []

    for tarifa in sitio.tarifas:
        tarifas.append({
            "aplica_para": tarifa.condicion,
            "precio": float(tarifa.precio),
            "condicion": tarifa.condicion,
        })

    return tarifas


def construir_entrada(sitio):
    return {
        "es_gratuito": sitio.es_gratuito,
        "texto": construir_entrada_resumen(sitio),
        "precio_min": sitio.precio.precio_min if sitio.precio else None,
        "precio_max": sitio.precio.precio_max if sitio.precio else None,
        "etiqueta_precio": sitio.precio.etiqueta_precio if sitio.precio else None,
        "tarifas": construir_tarifas(sitio),
    }


def construir_servicios(sitio):
    return {
        "wifi": sitio.tiene_wifi,
        "parqueadero": sitio.parqueadero,
        "permite_mascotas": sitio.permite_mascotas,
    }


def transformar_sitio_para_app(sitio):
    categoria = sitio.categoria.nombre if sitio.categoria else "Sin categoría"
    subcategoria = sitio.subcategoria.nombre if sitio.subcategoria else "Sin subcategoría"

    imagenes = [
        {
            "url": normalizar_url_imagen(media.url),
            "es_principal": media.es_principal,
        }
        for media in sitio.media
    ]

    imagenes.sort(key=lambda x: not x["es_principal"])

    return {
        "id_sitio": sitio.id_sitio,
        "nombre": sitio.nombre,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "direccion": construir_direccion(sitio),
        "horario_resumen": construir_horario_resumen(sitio.horario),
        "entrada_resumen": construir_entrada_resumen(sitio),
        "accesibilidad_resumen": construir_accesibilidad_resumen(sitio),
        "descripcion_corta": sitio.descripcion_corta,
        "entrada": construir_entrada(sitio),
        "servicios": construir_servicios(sitio),
        "imagenes": imagenes,
    }
