import apiClient from "../api/client";

export async function loginUsuario(payload) {
  const { data } = await apiClient.post("/auth/login", payload);
  return data;
}

export async function renovarToken() {
  const { data } = await apiClient.post("/auth/refresh");
  return data;
}

export async function renovarSesionAdmin() {
  const { data } = await apiClient.post("/auth/admin-session/refresh");
  return data;
}

export async function cerrarSesion() {
  const { data } = await apiClient.post("/auth/logout");
  return data;
}

export async function obtenerUsuarioActual() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}

export async function solicitarCodigoAdmin(username) {
  const { data } = await apiClient.post("/auth/correo/verificacion", {
    proposito: "login_2fa",
    username,
  });
  return data;
}

export async function reenviarCodigoAdmin(username) {
  const { data } = await apiClient.post("/auth/correo/reenviar", {
    proposito: "login_2fa",
    username,
  });
  return data;
}

export async function solicitarRecuperacionPassword(email) {
  const { data } = await apiClient.post("/auth/recuperacion/password/solicitar", {
    email,
  });
  return data;
}

export async function confirmarRecuperacionPassword(payload) {
  const { data } = await apiClient.post("/auth/recuperacion/password/confirmar", payload);
  return data;
}

export async function solicitarRecordatorioUsuario(email) {
  const { data } = await apiClient.post("/auth/recuperacion/usuario/solicitar", {
    email,
  });
  return data;
}
