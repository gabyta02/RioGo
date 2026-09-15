import apiClient from "../../core/api/client";

export async function obtenerRegistroAcciones(filters) {
  const response = await apiClient.get("/admin/registro-acciones", {
    params: {
      q: filters.q || undefined,
      usuario: filters.usuario || undefined,
      vista: filters.vista || "acciones",
      modulo: filters.modulo || "all",
      accion: filters.accion || "all",
      resultado: filters.resultado || "all",
      fecha_inicio: filters.fecha_inicio || undefined,
      fecha_fin: filters.fecha_fin || undefined,
      page: filters.page || 1,
      page_size: filters.page_size || 10,
    },
  });
  return response.data;
}

export async function obtenerCatalogosRegistroAcciones() {
  const response = await apiClient.get("/admin/registro-acciones/catalogos");
  return response.data;
}

export async function obtenerDetalleRegistroAccion(idEvento, vista = "acciones") {
  const response = await apiClient.get(`/admin/registro-acciones/${idEvento}`, {
    params: { vista },
  });
  return response.data;
}
