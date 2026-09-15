import apiClient from "../../core/api/client";

export const routeTypes = ["Senderismo", "Ciclismo", "Caminata Urbana", "Montañismo", "Otras"];

export async function obtenerRutas(filters) {
  const response = await apiClient.get("/admin/rutas-turisticas", {
    params: {
      q: filters.q || undefined,
      tipo_ruta: filters.tipo_ruta || undefined,
      estado: filters.estado || "all",
      page: filters.page || 1,
      page_size: filters.page_size || 10,
    },
  });
  return response.data;
}

export async function crearRuta(payload) {
  const response = await apiClient.post("/admin/rutas-turisticas", payload);
  return response.data;
}

export async function subirImagenRuta(tituloRuta, archivo) {
  const data = new FormData();
  data.append("titulo_ruta", tituloRuta);
  data.append("archivo", archivo);
  const response = await apiClient.post("/admin/rutas-turisticas/imagen", data, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function actualizarRuta(idRuta, payload) {
  const response = await apiClient.patch(`/admin/rutas-turisticas/${idRuta}`, payload);
  return response.data;
}

export async function eliminarRuta(idRuta) {
  const response = await apiClient.delete(`/admin/rutas-turisticas/${idRuta}`);
  return response.data;
}

export async function cambiarEstadoRuta(idRuta, activo) {
  const response = await apiClient.patch(`/admin/rutas-turisticas/${idRuta}/estado`, { activo });
  return response.data;
}

export async function buscarSitiosRuta(q) {
  const response = await apiClient.get("/admin/rutas-turisticas/sitios", {
    params: { q: q || undefined, limit: 20 },
  });
  return response.data;
}

export async function obtenerGeometriaRuta(idRuta) {
  const response = await apiClient.get(`/admin/rutas-turisticas/${idRuta}/geometria`);
  return response.data;
}

export async function guardarGeometriaRuta(idRuta, payload) {
  const response = await apiClient.put(`/admin/rutas-turisticas/${idRuta}/geometria`, payload);
  return response.data;
}
