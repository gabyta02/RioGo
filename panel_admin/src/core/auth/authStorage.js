const SESSION_KEY = "riobambatour_admin_session";
export const AUTH_SESSION_EXPIRED_EVENT = "riobambatour:session-expired";
const ROLES_PANEL = new Set(["super-admin", "admin"]);

const TOKEN_REFRESH_IN_DEFAULT = 30 * 60 * 1000;
const INACTIVITY_MAX_DEFAULT = 30 * 60 * 1000;
const TOKEN_REFRESH_SAFETY_MS = 60 * 1000;
const TOKEN_REFRESH_MIN_MS = 30 * 1000;

// El API envía segundos; en localStorage guardamos milisegundos.
function aMilisegundos(valor, defaultMs) {
  if (valor == null) {
    return defaultMs;
  }

  if (valor < 86400) {
    return valor * 1000;
  }

  return valor;
}

function normalizarSesion(sesion) {
  if (!sesion) {
    return null;
  }

  const accessToken = sesion.access_token || sesion.token;
  const now = Date.now();
  const tokenRefreshInMs = calcularTokenRefreshMs(sesion);
  const inactivityMaxMs = aMilisegundos(
    sesion.inactividad_max_segundos,
    INACTIVITY_MAX_DEFAULT,
  );
  const lastActivityAt = sesion.last_activity_at || now;
  const lastAdminRefreshAt = sesion.last_admin_session_refresh_at || now;

  return {
    ...sesion,
    access_token: accessToken,
    token: accessToken,
    token_refresh_in: tokenRefreshInMs,
    inactividad_max_segundos: inactivityMaxMs,
    last_activity_at: lastActivityAt,
    last_admin_session_refresh_at: lastAdminRefreshAt,
    admin_session_refresh_at: sesion.admin_session_refresh_at || lastAdminRefreshAt + inactivityMaxMs,
    next_token_refresh: sesion.next_token_refresh || now + tokenRefreshInMs,
    inactivity_expires_at: sesion.inactivity_expires_at || lastActivityAt + inactivityMaxMs,
  };
}

function calcularTokenRefreshMs(sesion) {
  const requestedRefreshMs = aMilisegundos(sesion.token_refresh_in, TOKEN_REFRESH_IN_DEFAULT);
  const accessTtlMs = sesion.expires_in == null ? null : aMilisegundos(sesion.expires_in, requestedRefreshMs);

  if (!accessTtlMs || accessTtlMs <= TOKEN_REFRESH_SAFETY_MS) {
    return requestedRefreshMs;
  }

  return Math.max(TOKEN_REFRESH_MIN_MS, Math.min(requestedRefreshMs, accessTtlMs - TOKEN_REFRESH_SAFETY_MS));
}

export function leerSesionAlmacenada() {
  const rawSession = localStorage.getItem(SESSION_KEY);
  if (!rawSession) {
    return null;
  }

  try {
    return normalizarSesion(JSON.parse(rawSession));
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

export function esSesionPanel(sesion) {
  return Boolean(sesion?.rol && ROLES_PANEL.has(sesion.rol));
}

export function enriquecerSesionDesdePerfil(baseSession, perfil) {
  const usuario = {
    ...(baseSession.usuario || {}),
    id_usuario: perfil.id_usuario ?? baseSession.usuario?.id_usuario,
    username: perfil.username ?? baseSession.usuario?.username,
    email: perfil.email ?? baseSession.usuario?.email,
    nombre_completo: perfil.nombre_completo ?? baseSession.usuario?.nombre_completo,
    cargo_nombre: perfil.cargo_nombre ?? baseSession.usuario?.cargo_nombre,
    foto_url: perfil.foto_url ?? baseSession.usuario?.foto_url,
    autentificacion_doble: perfil.autentificacion_doble ?? baseSession.usuario?.autentificacion_doble,
    rol: perfil.rol ?? baseSession.usuario?.rol,
    activo: perfil.activo ?? baseSession.usuario?.activo,
  };

  return {
    ...baseSession,
    ...perfil,
    usuario,
    permisos_detalle: perfil.permisos,
    permisos: Array.isArray(perfil.permisos)
      ? perfil.permisos.map((item) => item.modulo)
      : baseSession.permisos,
    sitios_asignados: perfil.sitios_asignados || [],
  };
}

export function actualizarPermisosSesion(perfil) {
  const rawSession = localStorage.getItem(SESSION_KEY);
  if (!rawSession) {
    return null;
  }

  let sesionAlmacenada;
  try {
    sesionAlmacenada = JSON.parse(rawSession);
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }

  const sesionActualizada = enriquecerSesionDesdePerfil(sesionAlmacenada, perfil);
  localStorage.setItem(SESSION_KEY, JSON.stringify(sesionActualizada));
  return normalizarSesion(sesionActualizada);
}

export function guardarSesionTrasRefresh(newSession) {
  const sesionPrevia = obtenerSesion();
  guardarSesion({
    ...newSession,
    last_activity_at: sesionPrevia?.last_activity_at,
    inactivity_expires_at: sesionPrevia?.inactivity_expires_at,
    last_admin_session_refresh_at: sesionPrevia?.last_admin_session_refresh_at,
    admin_session_refresh_at: sesionPrevia?.admin_session_refresh_at,
    admin_sesion_id: newSession.admin_sesion_id || sesionPrevia?.admin_sesion_id,
    id_sesion: newSession.id_sesion || sesionPrevia?.id_sesion,
    permisos: sesionPrevia?.permisos ?? newSession.permisos,
    permisos_detalle: sesionPrevia?.permisos_detalle,
    sitios_asignados: sesionPrevia?.sitios_asignados ?? [],
  });
}

function modulosPermitidos(sesion) {
  if (!esSesionPanel(sesion)) {
    return [];
  }

  if (sesion.rol === "super-admin") {
    return null;
  }

  if (Array.isArray(sesion.permisos_detalle) && sesion.permisos_detalle.length) {
    return sesion.permisos_detalle.map((permiso) => permiso.modulo);
  }

  if (!Array.isArray(sesion.permisos)) {
    return [];
  }

  if (sesion.permisos.length && typeof sesion.permisos[0] === "object") {
    return sesion.permisos.map((permiso) => permiso.modulo);
  }

  return sesion.permisos;
}

export function tieneAccion(sesion, modulo, accion) {
  if (!esSesionPanel(sesion)) {
    return false;
  }

  if (sesion.rol === "super-admin") {
    return true;
  }

  // Los permisos pueden venir como catálogo enriquecido o como arreglo simple legado.
  // Mantener ambas formas evita romper sesiones guardadas antes de refrescar perfil.
  const detalle = sesion.permisos_detalle || sesion.permisos;
  if (!Array.isArray(detalle)) {
    return false;
  }

  const permiso = detalle.find((item) =>
  (typeof item === "string" ? item === modulo : item.modulo === modulo));

  if (!permiso) {
    return false;
  }

  if (typeof permiso === "string") {
    return accion === "ver";
  }

  return Array.isArray(permiso.acciones) && permiso.acciones.includes(accion);
}

export function tieneAlcanceSitio(sesion) {
  if (!esSesionPanel(sesion) || sesion.rol === "super-admin") {
    return false;
  }

  // Un dueño trabaja con permisos acotados a sus sitios asignados, no con gestión global.
  if (sesion.sitios_asignados?.length) {
    return true;
  }

  return (sesion.permisos_detalle || []).some((permiso) => permiso.alcance === "sitio");
}

export function esDuenoSitio(sesion) {
  const cargo = (
    sesion?.usuario?.cargo_nombre ||
    sesion?.cargo_nombre ||
    ""
  ).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

  return cargo === "dueno";
}

export function sinSitiosAsignados(sesion) {
  return tieneAlcanceSitio(sesion) && !(sesion.sitios_asignados?.length);
}

export function puedeAccederVista(sesion, viewId) {
  if (!esSesionPanel(sesion)) {
    return false;
  }

  if (viewId === "admin_accounts") {
    return sesion.rol === "super-admin";
  }

  const modulos = modulosPermitidos(sesion);
  if (modulos === null) {
    return true;
  }

  return modulos.includes(viewId);
}

export function primeraVistaPermitida(sesion) {
  const orden = [
    "dashboard",
    "analytics",
    "attractions",
    "categories",
    "routes",
    "chatbot_content",
    "noticias",
    "action_log",
    "admin_accounts",
  ];

  return orden.find((viewId) => puedeAccederVista(sesion, viewId)) || null;
}

export function guardarSesion(sesion) {
  const now = Date.now();
  const sesionPrevia = obtenerSesion();
  const tokenRefreshInMs = calcularTokenRefreshMs(sesion);
  const inactivityMaxMs = aMilisegundos(
    sesion.inactividad_max_segundos,
    INACTIVITY_MAX_DEFAULT,
  );
  const lastActivityAt = sesion.last_activity_at ?? sesionPrevia?.last_activity_at ?? now;
  const lastAdminRefreshAt = sesion.last_admin_session_refresh_at ?? sesionPrevia?.last_admin_session_refresh_at ?? now;

  const sesionConTimestamps = {
    ...sesion,
    token_refresh_in: tokenRefreshInMs,
    inactividad_max_segundos: inactivityMaxMs,
    last_activity_at: lastActivityAt,
    last_admin_session_refresh_at: lastAdminRefreshAt,
    admin_session_refresh_at: sesion.admin_session_refresh_at ?? sesionPrevia?.admin_session_refresh_at ?? lastAdminRefreshAt + inactivityMaxMs,
    next_token_refresh: now + tokenRefreshInMs,
    inactivity_expires_at: lastActivityAt + inactivityMaxMs,
  };

  localStorage.setItem(SESSION_KEY, JSON.stringify(sesionConTimestamps));
}

export function registrarActividadSesion() {
  const rawSession = localStorage.getItem(SESSION_KEY);
  if (!rawSession) {
    return null;
  }

  let sesionAlmacenada;
  try {
    sesionAlmacenada = JSON.parse(rawSession);
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }

  const now = Date.now();
  const inactivityMaxMs = aMilisegundos(
    sesionAlmacenada.inactividad_max_segundos,
    INACTIVITY_MAX_DEFAULT,
  );
  const sesionActualizada = {
    ...sesionAlmacenada,
    inactividad_max_segundos: inactivityMaxMs,
    last_activity_at: now,
    inactivity_expires_at: now + inactivityMaxMs,
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(sesionActualizada));
  return normalizarSesion(sesionActualizada);
}

export function registrarRenovacionSesionAdmin() {
  const rawSession = localStorage.getItem(SESSION_KEY);
  if (!rawSession) {
    return null;
  }

  let sesionAlmacenada;
  try {
    sesionAlmacenada = JSON.parse(rawSession);
  } catch {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }

  const now = Date.now();
  const inactivityMaxMs = aMilisegundos(
    sesionAlmacenada.inactividad_max_segundos,
    INACTIVITY_MAX_DEFAULT,
  );
  const sesionActualizada = {
    ...sesionAlmacenada,
    inactividad_max_segundos: inactivityMaxMs,
    last_admin_session_refresh_at: now,
    admin_session_refresh_at: now + inactivityMaxMs,
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(sesionActualizada));
  return normalizarSesion(sesionActualizada);
}

export function obtenerSesion() {
  const sesion = leerSesionAlmacenada();
  if (sesion?.inactivity_expires_at && Date.now() >= sesion.inactivity_expires_at) {
    localStorage.removeItem(SESSION_KEY);
    return null;
  }
  return sesion;
}

export function limpiarSesion() {
  localStorage.removeItem(SESSION_KEY);
}

export function notificarSesionExpirada(
  motivo = "Tu sesión se cerró por inactividad. Inicia sesión nuevamente.",
) {
  limpiarSesion();
  window.dispatchEvent(
    new CustomEvent(AUTH_SESSION_EXPIRED_EVENT, {
      detail: { motivo },
    }),
  );
}
