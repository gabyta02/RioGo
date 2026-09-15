import apiClient from "../../core/api/client";

export async function obtenerCuentasAdmin(filters) {
  const { data } = await apiClient.get("/admin/cuentas", {
    params: {
      q: filters.q || undefined,
      id_cargo: filters.id_cargo || undefined,
      activo:
        filters.estado === "activo"
          ? true
          : filters.estado === "inactivo"
            ? false
            : undefined,
      page: filters.page || 1,
      page_size: filters.page_size || 10,
    },
  });
  return data;
}

export async function obtenerCuentaAdmin(idUsuario) {
  const { data } = await apiClient.get(`/admin/cuentas/${idUsuario}`);
  return data;
}

export async function crearCuentaAdmin(payload) {
  const { data } = await apiClient.post("/admin/cuentas", payload);
  return data;
}

export async function actualizarCuentaAdmin(idUsuario, payload) {
  const { data } = await apiClient.patch(`/admin/cuentas/${idUsuario}`, payload);
  return data;
}

export async function cambiarEstadoCuentaAdmin(idUsuario, activo) {
  const { data } = await apiClient.patch(`/admin/cuentas/${idUsuario}/estado`, { activo });
  return data;
}

export async function eliminarCuentaAdmin(idUsuario) {
  const { data } = await apiClient.delete(`/admin/cuentas/${idUsuario}`);
  return data;
}

export async function obtenerCargos() {
  const { data } = await apiClient.get("/admin/cargos");
  return data;
}

export async function obtenerCargo(idCargo) {
  const { data } = await apiClient.get(`/admin/cargos/${idCargo}`);
  return data;
}

export async function obtenerPermisosCatalogo() {
  const { data } = await apiClient.get("/admin/permisos");
  return data;
}

export async function obtenerSitiosCuenta(idUsuario) {
  const { data } = await apiClient.get(`/admin/cuentas/${idUsuario}/sitios`);
  return data;
}

export async function obtenerCatalogoSitiosCuenta(filters = {}) {
  const { data } = await apiClient.get("/admin/cuentas/catalogo/sitios", {
    params: {
      q: filters.q || undefined,
      estado: filters.estado || "activo",
      page: filters.page || 1,
      page_size: filters.page_size || 100,
    },
  });
  return data;
}

export async function actualizarSitiosCuenta(idUsuario, sitios) {
  const { data } = await apiClient.put(`/admin/cuentas/${idUsuario}/sitios`, { sitios });
  return data;
}
