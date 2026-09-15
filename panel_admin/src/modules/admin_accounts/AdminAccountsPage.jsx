import { useEffect, useMemo, useState } from "react";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import Panel from "../../core/ui/Panel";
import PanelToolbar from "../../core/ui/PanelToolbar";
import SearchBox from "../../core/ui/SearchBox";
import AdminModal from "../../core/ui/AdminModal";
import {
  AdminActionButton,
  FormField,
  SelectFilter,
  TableActionButton,
  TimedAlert,
  ToggleRow,
  formInputClass,
} from "../../core/ui/AdminControls";
import { EditIcon, PlusIcon, TrashIcon } from "../../core/ui/icons";
import { getApiErrorMessage } from "../../core/api/errors";
import {
  actualizarCuentaAdmin,
  actualizarSitiosCuenta,
  cambiarEstadoCuentaAdmin,
  crearCuentaAdmin,
  eliminarCuentaAdmin,
  obtenerCargo,
  obtenerCargos,
  obtenerCuentaAdmin,
  obtenerCuentasAdmin,
  obtenerPermisosCatalogo,
  obtenerSitiosCuenta,
} from "./adminAccountsService";
import {
  buildPermisosState,
  esCargoDueno,
  esNombreCargoDueno,
  modulosVisiblesEnFormulario,
  obtenerTipoCargo,
  permisosCargoParaFormulario,
  permisosGlobalesParaPayload,
  permisosPorTipoCargo,
  permisosParaFormulario,
  validarSitiosDueno,
} from "./duenoPermissions";
import SitiosAsignadosSection from "./SitiosAsignadosSection";

function StatusBadge({ active }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-black ${
        active ? "bg-emerald-50 text-app-primario" : "bg-app-fondo text-app-texto-secundario"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${active ? "bg-app-primario" : "bg-app-borde"}`} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function formatUltimaActividad(value) {
  if (!value) {
    return "Sin registro";
  }

  const fecha = new Date(value);
  const diffMs = Date.now() - fecha.getTime();
  const minutos = Math.floor(diffMs / 60000);

  if (minutos < 1) return "Hace un momento";
  if (minutos < 60) return `Hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `Hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias === 1) return "Ayer";
  if (dias < 7) return `Hace ${dias} días`;
  const semanas = Math.floor(dias / 7);
  if (semanas < 5) return `Hace ${semanas} semanas`;
  return fecha.toLocaleDateString("es-EC");
}

function Pagination({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-app-borde px-4 py-3 text-sm">
      <p className="font-semibold text-app-texto-secundario">
        Mostrando {from}-{to} de {total} registros
      </p>
      <div className="flex items-center gap-2">
        <button
          className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario disabled:opacity-50"
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Anterior
        </button>
        <span className="grid h-9 min-w-9 place-items-center rounded-lg bg-app-primario px-3 text-sm font-black text-white">
          {page}
        </span>
        <button
          className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario disabled:opacity-50"
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}

function CuentaFormModal({ cuenta, cargos, catalogo, onClose, onSaved }) {
  const isEdit = Boolean(cuenta);
  const [form, setForm] = useState({
    nombre_completo: cuenta?.nombre_completo || "",
    email: cuenta?.email || "",
    id_cargo: cuenta?.id_cargo ? String(cuenta.id_cargo) : cargos[0] ? String(cargos[0].id_cargo) : "",
    activo: cuenta?.activo ?? true,
    permisos: buildPermisosState(catalogo, cuenta?.permisos || []),
    sitios: [],
  });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(isEdit);
  const [sitiosError, setSitiosError] = useState("");
  const [sitiosAsignadosDetalle, setSitiosAsignadosDetalle] = useState([]);

  const esDueno = esCargoDueno(cargos, form.id_cargo);
  const tipoCargo = obtenerTipoCargo(cargos, form.id_cargo);
  const permisosBloqueados = tipoCargo === "dueno" || tipoCargo === "usuario" || tipoCargo === "super_admin";
  const modulosFormulario = useMemo(
    () => modulosVisiblesEnFormulario(catalogo, esDueno, tipoCargo),
    [catalogo, esDueno, tipoCargo],
  );

  useEffect(() => {
    if (!isEdit || !cuenta?.id_usuario) {
      return undefined;
    }

    let isActive = true;
    obtenerCuentaAdmin(cuenta.id_usuario)
      .then((detalle) => {
        if (!isActive) return;
        const dueno = esCargoDueno(cargos, detalle.id_cargo);
        const tipo = obtenerTipoCargo(cargos, detalle.id_cargo);
        setForm({
          nombre_completo: detalle.nombre_completo,
          email: detalle.email,
          id_cargo: String(detalle.id_cargo || ""),
          activo: detalle.activo,
          permisos: permisosParaFormulario(catalogo, detalle.permisos, dueno, tipo),
          sitios: [],
        });
        return obtenerSitiosCuenta(cuenta.id_usuario);
      })
      .then((sitiosResponse) => {
        if (!isActive || !sitiosResponse) return;
        setSitiosAsignadosDetalle(sitiosResponse.items || []);
        setForm((current) => ({
          ...current,
          sitios: sitiosResponse.sitios || [],
        }));
      })
      .catch((err) => {
        if (isActive) setError(getApiErrorMessage(err));
      })
      .finally(() => {
        if (isActive) setIsLoading(false);
      });

    return () => {
      isActive = false;
    };
  }, [catalogo, cuenta, cargos, isEdit]);

  async function handleCargoChange(idCargo) {
    const seraDueno = esCargoDueno(cargos, idCargo);
    const tipo = obtenerTipoCargo(cargos, idCargo);
    setSitiosError("");
    setSitiosAsignadosDetalle([]);
    setForm((current) => ({
      ...current,
      id_cargo: idCargo,
      sitios: seraDueno ? current.sitios : [],
    }));
    if (!idCargo) return;

    try {
      const cargo = await obtenerCargo(Number(idCargo));
      setForm((current) => ({
        ...current,
        id_cargo: idCargo,
        permisos: permisosCargoParaFormulario(catalogo, cargo.permisos, seraDueno, tipo),
        sitios: seraDueno ? current.sitios : [],
      }));
    } catch (err) {
      setError(getApiErrorMessage(err));
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.id_cargo) {
      setError("Debes seleccionar un cargo para la cuenta");
      return;
    }
    const dueno = esCargoDueno(cargos, form.id_cargo);
    const errorSitios = dueno ? validarSitiosDueno(form.sitios) : "";
    if (errorSitios) {
      setSitiosError(errorSitios);
      setError(errorSitios);
      return;
    }

    setError("");
    setSitiosError("");
    setIsSaving(true);

    const payload = {
      nombre_completo: form.nombre_completo.trim(),
      email: form.email.trim(),
      id_cargo: Number(form.id_cargo),
      activo: form.activo,
      permisos: permisosPorTipoCargo(
        catalogo,
        permisosGlobalesParaPayload(form.permisos, dueno),
        obtenerTipoCargo(cargos, form.id_cargo),
      ),
    };

    try {
      if (isEdit) {
        await actualizarCuentaAdmin(cuenta.id_usuario, payload);
        if (dueno) {
          await actualizarSitiosCuenta(cuenta.id_usuario, form.sitios);
        } else {
          await actualizarSitiosCuenta(cuenta.id_usuario, []);
        }
      } else {
        const creada = await crearCuentaAdmin(payload);
        if (dueno) {
          await actualizarSitiosCuenta(creada.id_usuario, form.sitios);
        }
      }
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AdminModal
      error={error}
      isSaving={isSaving || isLoading}
      maxWidth={esDueno ? "max-w-3xl" : "max-w-2xl"}
      onClose={onClose}
      onDismissError={() => setError("")}
      onSubmit={handleSubmit}
      submitLabel={isEdit ? "Guardar cuenta" : "Guardar cuenta"}
      subtitle={
        esDueno
          ? "Datos de acceso, permisos por módulo y asignación obligatoria de sitios"
          : "Datos de acceso y permisos por módulo"
      }
      title="Cuenta administrativa"
    >
      <FormField label="Nombre completo">
        <input
          className={formInputClass}
          required
          value={form.nombre_completo}
          onChange={(event) => setForm((current) => ({ ...current, nombre_completo: event.target.value }))}
        />
      </FormField>
      <FormField label="Correo">
        <input
          className={formInputClass}
          required
          type="email"
          value={form.email}
          onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
        />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <FormField label="Rol">
          <select
            className={formInputClass}
            required
            value={form.id_cargo}
            onChange={(event) => handleCargoChange(event.target.value)}
          >
            {cargos.map((cargo) => (
              <option key={cargo.id_cargo} value={cargo.id_cargo}>
                {cargo.nombre}
              </option>
            ))}
          </select>
        </FormField>
        <ToggleRow
          checked={form.activo}
          onChange={(activo) => setForm((current) => ({ ...current, activo }))}
        >
          Cuenta activa
        </ToggleRow>
      </div>
      <div className="space-y-2">
        <p className="text-sm font-black text-app-texto-primario">Permisos por módulo</p>
        {esDueno ? (
          <p className="text-xs font-semibold text-app-texto-secundario">
            El acceso a atractivos y contenido chatbot se define en Sitios asignados.
          </p>
        ) : null}
        {tipoCargo === "usuario" ? (
          <p className="rounded-lg border border-app-borde bg-app-fondo px-4 py-3 text-sm font-semibold text-app-texto-secundario">
            El rol Usuario corresponde al aplicativo móvil y no recibe permisos del panel administrativo.
          </p>
        ) : null}
        {modulosFormulario.map((item) => (
          <ToggleRow
            key={item.codigo}
            checked={Boolean(form.permisos[item.codigo])}
            onChange={(activo) => {
              if (permisosBloqueados) return;
              setForm((current) => ({
                ...current,
                permisos: { ...current.permisos, [item.codigo]: activo },
              }));
            }}
          >
            {item.nombre}
          </ToggleRow>
        ))}
      </div>
      {esDueno ? (
        <SitiosAsignadosSection
          error={sitiosError}
          requerido
          sitiosAsignados={form.sitios}
          sitiosAsignadosDetalleInicial={sitiosAsignadosDetalle}
          onChange={(sitios) => {
            setSitiosError("");
            setForm((current) => ({ ...current, sitios }));
          }}
        />
      ) : null}
    </AdminModal>
  );
}

export default function AdminAccountsPage() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [filters, setFilters] = useState({
    q: "",
    id_cargo: "",
    estado: "all",
    page: 1,
    page_size: 10,
  });
  const [cargos, setCargos] = useState([]);
  const [catalogo, setCatalogo] = useState([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    let isActive = true;
    Promise.all([obtenerCargos(), obtenerPermisosCatalogo()])
      .then(([cargosResponse, permisosResponse]) => {
        if (!isActive) return;
        setCargos(cargosResponse);
        setCatalogo(permisosResponse);
      })
      .catch((err) => {
        if (isActive) setError(getApiErrorMessage(err));
      });
    return () => {
      isActive = false;
    };
  }, []);

  useEffect(() => {
    let isActive = true;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await obtenerCuentasAdmin(filters);
        if (isActive) setData(response);
      } catch (err) {
        if (isActive) setError(getApiErrorMessage(err));
      } finally {
        if (isActive) setIsLoading(false);
      }
    }, 250);
    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [filters, refreshToken]);

  const cargoOptions = useMemo(
    () => [
      { value: "", label: "Rol" },
      ...cargos.map((cargo) => ({ value: String(cargo.id_cargo), label: cargo.nombre })),
    ],
    [cargos],
  );

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
  }

  function handleSaved() {
    setModal(null);
    setRefreshToken((current) => current + 1);
  }

  function requestToggleStatus(cuenta) {
    const nextActive = !cuenta.activo;
    setConfirmAction({
      title: nextActive ? "Activar cuenta" : "Inactivar cuenta",
      message: `¿${nextActive ? "Activar" : "Inactivar"} la cuenta de ${cuenta.nombre_completo}?`,
      confirmLabel: nextActive ? "Activar" : "Inactivar",
      run: async () => cambiarEstadoCuentaAdmin(cuenta.id_usuario, nextActive),
    });
  }

  function requestDelete(cuenta) {
    setConfirmAction({
      title: "Eliminar cuenta",
      message: `Se eliminará permanentemente la cuenta de ${cuenta.nombre_completo}.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarCuentaAdmin(cuenta.id_usuario),
    });
  }

  async function executeConfirmAction() {
    if (!confirmAction) return;
    setIsConfirming(true);
    try {
      await confirmAction.run();
      setConfirmAction(null);
      handleSaved();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    <div className="space-y-5">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <Panel>
        <PanelToolbar
          search={
            <SearchBox
              label="Buscar administrador"
              placeholder="Buscar administrador..."
              value={filters.q}
              onChange={(value) => updateFilter("q", value)}
            />
          }
          filters={
            <>
              <SelectFilter
                icon
                label="Rol"
                options={cargoOptions}
                value={filters.id_cargo}
                onChange={(value) => updateFilter("id_cargo", value)}
              />
              <SelectFilter
                icon
                label="Estado"
                options={[
                  { value: "all", label: "Estado" },
                  { value: "activo", label: "Activo" },
                  { value: "inactivo", label: "Inactivo" },
                ]}
                value={filters.estado}
                onChange={(value) => updateFilter("estado", value)}
              />
            </>
          }
          actions={
            <AdminActionButton
              icon={<PlusIcon />}
              variant="primary"
              onClick={() => setModal({ type: "create" })}
            >
              Nueva cuenta
            </AdminActionButton>
          }
        />

        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-app-fondo text-xs font-black uppercase text-app-texto-secundario">
              <tr>
                <th className="min-w-[280px] px-4 py-3">Administrador</th>
                <th className="px-4 py-3">Rol</th>
                <th className="px-4 py-3">Última actividad</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-borde">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={5}>
                    Cargando cuentas...
                  </td>
                </tr>
              ) : data.items.length ? (
                data.items.map((cuenta) => (
                  <tr key={cuenta.id_usuario}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-app-primario-claro text-xs font-black text-app-primario">
                          {cuenta.iniciales}
                        </span>
                        <div>
                          <p className="font-black text-app-texto-primario">{cuenta.nombre_completo}</p>
                          <p className="mt-1 text-xs font-semibold text-app-texto-secundario">{cuenta.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-semibold text-app-texto-secundario">
                        {cuenta.cargo_nombre || "Sin cargo"}
                      </p>
                      {esNombreCargoDueno(cuenta.cargo_nombre) ? (
                        <span className="mt-1 inline-flex rounded-full bg-app-primario-claro px-2 py-0.5 text-[11px] font-black text-app-primario">
                          Solo sitios asignados
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 font-semibold text-app-texto-secundario">
                      {formatUltimaActividad(cuenta.ultimo_acceso_en)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        className="rounded-full focus:outline-none focus:ring-4 focus:ring-app-primario-claro"
                        type="button"
                        onClick={() => requestToggleStatus(cuenta)}
                      >
                        <StatusBadge active={cuenta.activo} />
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <TableActionButton icon={<EditIcon />} onClick={() => setModal({ type: "edit", cuenta })}>
                          Editar
                        </TableActionButton>
                        <TableActionButton icon={<TrashIcon />} variant="danger" onClick={() => requestDelete(cuenta)}>
                          Eliminar
                        </TableActionButton>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={5}>
                    No hay cuentas con los filtros seleccionados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
        />
      </Panel>

      {modal ? (
        <CuentaFormModal
          cuenta={modal.cuenta}
          cargos={cargos}
          catalogo={catalogo}
          onClose={() => setModal(null)}
          onSaved={handleSaved}
        />
      ) : null}

      {confirmAction ? (
        <ConfirmDialog
          confirmLabel={confirmAction.confirmLabel}
          isLoading={isConfirming}
          message={confirmAction.message}
          onCancel={() => setConfirmAction(null)}
          onConfirm={executeConfirmAction}
          title={confirmAction.title}
        />
      ) : null}
    </div>
  );
}
