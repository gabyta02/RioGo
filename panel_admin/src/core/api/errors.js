const FIELD_LABELS = {
  username: "nombre de usuario",
  password: "contraseña",
  codigo_verificacion: "código de verificación",
  token_verificacion: "token de verificación",
  email: "correo electrónico",
  nombre_completo: "nombre completo",
  id_cargo: "cargo",
};

const DETAIL_TRANSLATIONS = [
  [/field required/i, "Este campo es obligatorio."],
  [/missing/i, "Falta completar un campo obligatorio."],
  [/value is not a valid/i, "El valor ingresado no tiene un formato válido."],
  [/input should be a valid/i, "El valor ingresado no tiene un formato válido."],
  [/string should have at least/i, "El texto ingresado es demasiado corto."],
  [/string should have at most/i, "El texto ingresado es demasiado largo."],
  [/ensure this value has at least/i, "El valor ingresado es demasiado corto."],
  [/ensure this value has at most/i, "El valor ingresado es demasiado largo."],
  [/unable to parse/i, "No se pudo interpretar el valor enviado."],
  [/network error/i, "No se pudo conectar con el servidor."],
  [/timeout/i, "La solicitud tardó demasiado. Intenta nuevamente."],
];

function formatFieldName(loc) {
  if (!Array.isArray(loc)) {
    return "";
  }

  const field = [...loc].reverse().find((item) => typeof item === "string");
  if (!field || ["body", "query", "path"].includes(field)) {
    return "";
  }

  return FIELD_LABELS[field] || field.replaceAll("_", " ");
}

function translateMessage(message) {
  const text = String(message || "").trim();
  if (!text) {
    return "";
  }

  const translation = DETAIL_TRANSLATIONS.find(([pattern]) => pattern.test(text));
  return translation ? translation[1] : text;
}

function formatValidationItem(item) {
  if (!item || typeof item !== "object") {
    return translateMessage(item);
  }

  const field = formatFieldName(item.loc);
  const message = translateMessage(item.msg || item.message || item.detail);

  if (field && message) {
    return `${field}: ${message}`;
  }
  return message;
}

export function getApiErrorMessage(error, fallback = "Ocurrió un error") {
  if (error?.response?.status === 403) {
    return "No tienes permisos para realizar esta acción.";
  }

  if (error?.response?.status === 401) {
    return "Usuario o contraseña incorrectos.";
  }

  if (error?.response?.status >= 500) {
    const detail = error?.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return translateMessage(detail);
    }
    return "Error interno del servidor. Intenta nuevamente o contacta al administrador.";
  }

  if (error?.code === "ERR_NETWORK" || !error?.response) {
    return "No se pudo conectar con el servidor. Revisa tu conexión e intenta nuevamente.";
  }

  const detail = error?.response?.data?.detail;

  if (Array.isArray(detail)) {
    const message = detail
      .map(formatValidationItem)
      .filter(Boolean)
      .join(". ");
    return message || fallback;
  }

  if (detail && typeof detail === "object") {
    return formatValidationItem(detail) || fallback;
  }

  return translateMessage(detail) || fallback;
}

export function needsTwoFactorCode(error) {
  if (error?.response?.status !== 400) {
    return false;
  }

  const detail = error?.response?.data?.detail;
  const text = Array.isArray(detail)
    ? detail.map((item) => item?.msg || "").join(" ")
    : String(detail || "");

  return text.includes("codigo_verificacion");
}
