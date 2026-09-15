export const MODULOS_EXCLUIDOS = new Set(["admin_accounts"]);

export const MODULOS_ALCANCE_SITIO = ["attractions", "chatbot_content"];
export const MODULOS_DUENO_GLOBAL = new Set(["dashboard", "analytics"]);

export const PERMISOS_POR_SITIO_INFO = [
  {
    modulo: "Atractivos turísticos",
    permisos: [
      "Ver sitio",
      "Editar sitio (datos generales, horarios, dirección, contacto, precios y multimedia)",
    ],
  },
  {
    modulo: "Contenido chatbot",
    permisos: [
      "Ver contenido del sitio",
      "Crear, actualizar y eliminar documentos",
      "Exportar contenido",
    ],
  },
];

export function normalizarNombreCargo(nombre) {
  return (nombre || "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .trim()
    .toLowerCase();
}

export function esCargoDueno(cargos, idCargo) {
  const cargo = cargos.find((item) => String(item.id_cargo) === String(idCargo));
  return normalizarNombreCargo(cargo?.nombre) === "dueno";
}

export function obtenerTipoCargo(cargos, idCargo) {
  const cargo = cargos.find((item) => String(item.id_cargo) === String(idCargo));
  const nombre = normalizarNombreCargo(cargo?.nombre);
  if (nombre === "dueno") return "dueno";
  if (nombre === "super admin" || nombre === "super administrador") return "super_admin";
  if (nombre === "admin") return "admin";
  if (nombre === "usuario") return "usuario";
  return "admin";
}

export function esNombreCargoDueno(nombre) {
  return normalizarNombreCargo(nombre) === "dueno";
}

export function buildPermisosState(catalogo, activos = []) {
  const activosSet = new Set(activos);
  return Object.fromEntries(
    catalogo
      .filter((item) => !MODULOS_EXCLUIDOS.has(item.codigo))
      .map((item) => [item.codigo, activosSet.has(item.codigo)]),
  );
}

export function permisosActivos(permisosMap) {
  return Object.entries(permisosMap)
    .filter(([, activo]) => activo)
    .map(([codigo]) => codigo);
}

export function permisosGlobalesParaPayload(permisosMap, esDueno) {
  const activos = permisosActivos(permisosMap);
  if (!esDueno) {
    return activos;
  }
  return activos.filter((codigo) => !MODULOS_ALCANCE_SITIO.includes(codigo));
}

export function permisosPorTipoCargo(catalogo, permisos, tipoCargo) {
  if (tipoCargo === "super_admin") {
    return catalogo
      .filter((item) => !MODULOS_EXCLUIDOS.has(item.codigo))
      .map((item) => item.codigo);
  }
  if (tipoCargo === "dueno") {
    return permisos.filter((codigo) => MODULOS_DUENO_GLOBAL.has(codigo));
  }
  if (tipoCargo === "usuario") {
    return [];
  }
  return permisos.filter((codigo) => !MODULOS_EXCLUIDOS.has(codigo));
}

export function permisosParaFormulario(catalogo, permisosApi, esDueno, tipoCargo = esDueno ? "dueno" : "admin") {
  const filtrados = permisosPorTipoCargo(catalogo, permisosApi, tipoCargo);
  return buildPermisosState(catalogo, filtrados);
}

export function permisosCargoParaFormulario(catalogo, permisosCargo, esDueno, tipoCargo = esDueno ? "dueno" : "admin") {
  const filtrados = permisosPorTipoCargo(catalogo, permisosCargo, tipoCargo);
  return buildPermisosState(catalogo, filtrados);
}

export function modulosVisiblesEnFormulario(catalogo, esDueno, tipoCargo = esDueno ? "dueno" : "admin") {
  return catalogo.filter((item) => {
    if (MODULOS_EXCLUIDOS.has(item.codigo)) {
      return false;
    }
    if (tipoCargo === "usuario") {
      return false;
    }
    if (tipoCargo === "dueno" && !MODULOS_DUENO_GLOBAL.has(item.codigo)) {
      return false;
    }
    return true;
  });
}

export function validarSitiosDueno(sitios) {
  if (sitios?.length) {
    return "";
  }
  return "Debes asignar al menos un sitio turístico para una cuenta con rol Dueño.";
}
