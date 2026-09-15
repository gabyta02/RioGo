import os


IMAGE_URL_PREFIX = "/api/v1/imagenes"
DEFAULT_SITE_IMAGE_URL_FALLBACK = "/api/v1/imagenes/default/site.jpg"

PREFIJOS_INTERNOS = (
    "/fuente_datos/imagenes/",
    "fuente_datos/imagenes/",
    "/api/v1/imagenes/",
    "api/v1/imagenes/",
    "/imagenes/",
    "imagenes/",
)


def _obtener_public_base_url() -> str:
    public_base_url = (os.getenv("PUBLIC_BASE_URL") or "").strip().rstrip("/")

    if not public_base_url.startswith(("http://", "https://")):
        raise RuntimeError(
            "PUBLIC_BASE_URL debe estar configurada y comenzar con http:// o https://"
        )

    return public_base_url


def _limpiar_ruta_relativa(valor: str) -> str:
    ruta = valor.strip()
    while "//" in ruta:
        ruta = ruta.replace("//", "/")

    for prefijo in PREFIJOS_INTERNOS:
        if ruta.startswith(prefijo):
            ruta = ruta[len(prefijo):]
            break

    partes = [parte for parte in ruta.split("/") if parte]
    return "/".join(partes)


def normalizar_url_imagen(valor: str | None) -> str:
    public_base_url = _obtener_public_base_url()
    default_site_image_url = (os.getenv("DEFAULT_SITE_IMAGE_URL") or "").strip()
    if not default_site_image_url:
        default_site_image_url = DEFAULT_SITE_IMAGE_URL_FALLBACK

    url = (valor or "").strip()
    if not url:
        url = default_site_image_url

    if url.startswith(("http://", "https://")):
        return url

    ruta_relativa = _limpiar_ruta_relativa(url)
    return f"{public_base_url}{IMAGE_URL_PREFIX}/{ruta_relativa}"
