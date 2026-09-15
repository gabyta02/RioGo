import re
import unicodedata


CONTROL_CHARS_RE = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u200b\u200c\u200d\ufeff]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
MULTISPACE_RE = re.compile(r"[ \t]+")
MARKDOWN_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+.!-])")
HEADING_PREFIX_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_UNDERSCORE_RE = re.compile(r"__(.+?)__")
LIST_MARKER_RE = re.compile(r"^[\-\*•]\s+", re.MULTILINE)
ORDERED_LIST_RE = re.compile(r"^\d+[\.\)]\s+", re.MULTILINE)


def _normalizar_markdown(texto: str) -> str:
    contenido = MARKDOWN_ESCAPE_RE.sub(r"\1", texto)

    prev = None
    while prev != contenido:
        prev = contenido
        contenido = BOLD_RE.sub(r"\1", contenido)
        contenido = ITALIC_UNDERSCORE_RE.sub(r"\1", contenido)

    contenido = HEADING_PREFIX_RE.sub("", contenido)
    return contenido


def limpiar_texto_para_embedding(texto: str | None) -> str:
    contenido = unicodedata.normalize("NFKC", str(texto or ""))
    contenido = contenido.replace("\r\n", "\n").replace("\r", "\n")
    contenido = CONTROL_CHARS_RE.sub("", contenido)
    contenido = HTML_TAG_RE.sub(" ", contenido)
    contenido = _normalizar_markdown(contenido)
    lineas = [
        MULTISPACE_RE.sub(" ", linea).strip()
        for linea in contenido.split("\n")
        if linea.strip()
    ]
    return "\n".join(lineas).strip()


def limpiar_texto_chunk(texto: str | None) -> str:
    """Texto plano continuo por sección, sin saltos de línea ni marcadores markdown."""
    contenido = limpiar_texto_para_embedding(texto)
    if not contenido:
        return ""

    contenido = LIST_MARKER_RE.sub("", contenido)
    contenido = ORDERED_LIST_RE.sub("", contenido)
    contenido = contenido.replace("\n", " ")
    contenido = contenido.replace("/", " ")
    contenido = contenido.replace("*", "")
    contenido = contenido.replace("#", "")
    contenido = MULTISPACE_RE.sub(" ", contenido)
    return contenido.strip()


def texto_tiene_contenido_util(texto: str | None) -> bool:
    limpio = limpiar_texto_para_embedding(texto)
    if not limpio:
        return False
    return bool(re.search(r"[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ]", limpio))
