import apiClient from "../../core/api/client";

export async function obtenerPerfil() {
  const { data } = await apiClient.get("/auth/me");
  return data;
}

export async function actualizarCuenta(payload) {
  const { data } = await apiClient.patch("/auth/cuenta", payload);
  return data;
}

export async function actualizar2FA(payload) {
  const { data } = await apiClient.patch("/auth/cuenta/2fa", payload);
  return data;
}

export async function subirFotoPerfil(archivo) {
  const formData = new FormData();
  formData.append("archivo", archivo);
  const { data } = await apiClient.post("/auth/cuenta/foto", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function solicitarCodigoVerificacion({ proposito, username }) {
  const { data } = await apiClient.post("/auth/correo/verificacion", {
    proposito,
    username,
  });
  return data;
}

export async function reenviarCodigoVerificacion({ proposito, username }) {
  const { data } = await apiClient.post("/auth/correo/reenviar", {
    proposito,
    username,
  });
  return data;
}
