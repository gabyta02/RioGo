import apiClient from "../../core/api/client";

export async function buscarEntidadesContenido(filters) {
  const response = await apiClient.get("/admin/contenido-chatbots/entidades", {
    params: {
      q: filters.q || undefined,
      tipo: filters.tipo || "all",
      limit: filters.limit || 20,
    },
  });
  return response.data;
}

export async function obtenerRepositoriosContenido() {
  const response = await apiClient.get("/admin/contenido-chatbots/repositorios");
  return response.data;
}

export async function crearRepositorioContenido(payload) {
  const response = await apiClient.post("/admin/contenido-chatbots/repositorios", payload);
  return response.data;
}

export async function renombrarRepositorioContenido(slug, payload) {
  const response = await apiClient.patch(`/admin/contenido-chatbots/repositorios/${slug}`, payload);
  return response.data;
}

export async function eliminarRepositorioContenido(slug) {
  const response = await apiClient.delete(`/admin/contenido-chatbots/repositorios/${slug}`);
  return response.data;
}

export async function crearDocumentoContenido(slug, payload) {
  const response = await apiClient.post(
    `/admin/contenido-chatbots/repositorios/${slug}/documentos`,
    payload,
  );
  return response.data;
}

export async function actualizarDocumentoContenido(idDocumento, payload) {
  const response = await apiClient.patch(`/admin/contenido-chatbots/documentos/${idDocumento}`, payload);
  return response.data;
}

export async function regenerarChunkDescripcion(payload) {
  const response = await apiClient.post("/admin/contenido-chatbots/chunks/descripcion", payload);
  return response.data;
}

export async function agregarContenidoDocumento(idDocumento, payload) {
  const response = await apiClient.put(
    `/admin/contenido-chatbots/documentos/${idDocumento}/contenido`,
    payload,
  );
  return response.data;
}

export async function obtenerContenidoDocumento(idDocumento) {
  const response = await apiClient.get(`/admin/contenido-chatbots/documentos/${idDocumento}/contenido`);
  return response.data;
}

export async function eliminarDocumentoContenido(idDocumento) {
  const response = await apiClient.delete(`/admin/contenido-chatbots/documentos/${idDocumento}`);
  return response.data;
}
