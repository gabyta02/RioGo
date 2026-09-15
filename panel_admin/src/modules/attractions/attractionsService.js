import apiClient from "../../core/api/client";

export async function obtenerCatalogosAtractivos() {
  const [categorias, subcategorias, parroquias, plataformas] = await Promise.all([
    apiClient.get("/admin/atractivos/categorias"),
    apiClient.get("/admin/atractivos/subcategorias"),
    apiClient.get("/admin/atractivos/parroquias"),
    apiClient.get("/admin/atractivos/plataformas"),
  ]);

  return {
    categorias: categorias.data,
    subcategorias: subcategorias.data,
    parroquias: parroquias.data,
    plataformas: plataformas.data,
  };
}

export async function obtenerAtractivos(filters) {
  const response = await apiClient.get("/admin/atractivos", {
    params: {
      q: filters.q || undefined,
      id_categoria: filters.id_categoria || undefined,
      id_subcategoria: filters.id_subcategoria || undefined,
      estado: filters.estado || "all",
      servicio: filters.servicio || "all",
      precio: filters.precio || "all",
      page: filters.page || 1,
      page_size: filters.page_size || 10,
    },
  });

  return response.data;
}

export async function crearAtractivo(payload) {
  const response = await apiClient.post("/admin/atractivos", payload);
  return response.data;
}

export async function obtenerDetalleAtractivo(idSitio) {
  const response = await apiClient.get(`/admin/atractivos/${idSitio}`);
  return response.data;
}

export async function actualizarAtractivo(idSitio, payload) {
  const response = await apiClient.put(`/admin/atractivos/${idSitio}`, payload);
  return response.data;
}

export async function eliminarAtractivo(idSitio) {
  const response = await apiClient.delete(`/admin/atractivos/${idSitio}`);
  return response.data;
}

export async function cambiarEstadoAtractivo(idSitio, activo) {
  const response = await apiClient.patch(`/admin/atractivos/${idSitio}/estado`, { activo });
  return response.data;
}

export async function subirImagenesAtractivo(nombreSitio, archivos) {
  const formData = new FormData();
  formData.append("nombre_sitio", nombreSitio);
  Array.from(archivos).forEach((archivo) => {
    formData.append("archivos", archivo);
  });

  const response = await apiClient.post("/admin/atractivos/imagenes", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}
