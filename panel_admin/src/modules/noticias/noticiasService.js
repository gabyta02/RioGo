import apiClient from "../../core/api/client";

export async function obtenerNoticias(filters) {
  const response = await apiClient.get("/admin/noticias", {
    params: {
      q: filters.q || undefined,
      estado: filters.estado || "all",
      page: filters.page || 1,
      page_size: filters.page_size || 12,
    },
  });
  return response.data;
}

export async function crearNoticia(payload) {
  const response = await apiClient.post("/admin/noticias", payload);
  return response.data;
}

export async function actualizarNoticia(idNoticia, payload) {
  const response = await apiClient.patch(`/admin/noticias/${idNoticia}`, payload);
  return response.data;
}

export async function eliminarNoticia(idNoticia) {
  const response = await apiClient.delete(`/admin/noticias/${idNoticia}`);
  return response.data;
}

export async function cambiarEstadoNoticia(idNoticia, activa) {
  const response = await apiClient.patch(`/admin/noticias/${idNoticia}/estado`, { activa });
  return response.data;
}

export async function subirImagenNoticia(tituloNoticia, archivo) {
  const data = new FormData();
  data.append("titulo_noticia", tituloNoticia);
  data.append("archivo", archivo);
  const response = await apiClient.post("/admin/noticias/imagen", data, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}
