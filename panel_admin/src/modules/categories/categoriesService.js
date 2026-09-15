import apiClient from "../../core/api/client";

export async function obtenerCategoriasDetalle() {
  const response = await apiClient.get("/admin/atractivos/categorias/detalle", {
    params: { incluir_inactivas: true },
  });
  return response.data;
}

export async function crearCategoria(payload) {
  const response = await apiClient.post("/admin/atractivos/categorias", payload);
  return response.data;
}

export async function actualizarCategoria(idCategoria, payload) {
  const response = await apiClient.patch(`/admin/atractivos/categorias/${idCategoria}`, payload);
  return response.data;
}

export async function eliminarCategoria(idCategoria) {
  const response = await apiClient.delete(`/admin/atractivos/categorias/${idCategoria}`);
  return response.data;
}

export async function cambiarEstadoCategoria(idCategoria, activo) {
  const response = await apiClient.patch(`/admin/atractivos/categorias/${idCategoria}/estado`, { activo });
  return response.data;
}

export async function crearSubcategoria(payload) {
  const response = await apiClient.post("/admin/atractivos/subcategorias", payload);
  return response.data;
}

export async function actualizarSubcategoria(idSubcategoria, payload) {
  const response = await apiClient.patch(
    `/admin/atractivos/subcategorias/${idSubcategoria}`,
    payload,
  );
  return response.data;
}

export async function eliminarSubcategoria(idSubcategoria) {
  const response = await apiClient.delete(`/admin/atractivos/subcategorias/${idSubcategoria}`);
  return response.data;
}

export async function cambiarEstadoSubcategoria(idSubcategoria, activo) {
  const response = await apiClient.patch(`/admin/atractivos/subcategorias/${idSubcategoria}/estado`, { activo });
  return response.data;
}
