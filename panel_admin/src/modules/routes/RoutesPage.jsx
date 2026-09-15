import { useEffect, useMemo, useState } from "react";
import AdminModal from "../../core/ui/AdminModal";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import {
  AdminActionButton,
  FormField,
  SelectFilter,
  TableActionButton,
  TimedAlert,
  ToggleRow,
  formInputClass,
  formTextareaClass,
} from "../../core/ui/AdminControls";
import Panel from "../../core/ui/Panel";
import SearchBox from "../../core/ui/SearchBox";
import { EditIcon, EyeIcon, PlusIcon, RouteIcon, TrashIcon } from "../../core/ui/icons";
import RouteGeometryPage from "./RouteGeometryPage";
import { actualizarRuta, cambiarEstadoRuta, crearRuta, eliminarRuta, obtenerRutas, routeTypes, subirImagenRuta } from "./routesService";
import { getApiErrorMessage } from "../../core/api/errors";
import { obtenerSesion, tieneAccion } from "../../core/auth/authStorage";

function StatusBadge({ active }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-black ${
        active
          ? "border-emerald-200 bg-emerald-50 text-app-primario"
          : "border-slate-200 bg-slate-100 text-app-texto-secundario"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-app-exito" : "bg-app-texto-secundario"}`} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function RouteFormModal({ onClose, onSaved, route }) {
  const [form, setForm] = useState({
    titulo: route?.titulo || "",
    tipo_ruta: route?.tipo_ruta || "Senderismo",
    descripcion: route?.descripcion || "",
    url_imagen: route?.url_imagen || "",
    activo: route?.activo ?? true,
  });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [previewImage, setPreviewImage] = useState("");
  const isEdit = Boolean(route);

  function updateField(key, value) {
    setError("");
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.titulo.trim()) {
      setError("Ingresa el título de la ruta");
      return;
    }
    if (!form.descripcion.trim()) {
      setError("Ingresa la descripción de la ruta");
      return;
    }
    if (!form.url_imagen.trim()) {
      setError("Agrega una imagen de referencia o su URL");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const payload = {
        titulo: form.titulo.trim(),
        tipo_ruta: form.tipo_ruta,
        descripcion: form.descripcion.trim(),
        url_imagen: form.url_imagen.trim(),
        activo: form.activo,
      };

      if (!isEdit) {
        await crearRuta(payload);
      } else {
        await actualizarRuta(route.id_ruta, payload);
      }

      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleImageUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!form.titulo.trim()) {
      setError("Primero ingresa el título de la ruta para subir la imagen");
      return;
    }
    setIsUploading(true);
    setError("");
    try {
      const uploaded = await subirImagenRuta(form.titulo.trim(), file);
      updateField("url_imagen", uploaded.url);
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <>
      <AdminModal
        error={error}
        isSaving={isSaving}
        onClose={onClose}
        onDismissError={() => setError("")}
        onSubmit={handleSubmit}
        submitLabel={isEdit ? "Guardar ruta" : "Crear ruta"}
        title={isEdit ? "Editar ruta turística" : "Nueva ruta turística"}
        maxWidth="max-w-2xl"
      >
        <FormField label="Título">
          <input
            className={formInputClass}
            maxLength={150}
            required
            value={form.titulo}
            onChange={(event) => updateField("titulo", event.target.value)}
          />
        </FormField>
        <FormField label="Tipo de ruta">
          <select
            className={formInputClass}
            value={form.tipo_ruta}
            onChange={(event) => updateField("tipo_ruta", event.target.value)}
          >
            {routeTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </FormField>
        <FormField label="URL de la imagen">
          <input
            className={formInputClass}
            placeholder="/api/v1/imagenes/rutas/ruta/imagen.jpg"
            value={form.url_imagen}
            onChange={(event) => updateField("url_imagen", event.target.value)}
          />
        </FormField>
        <label className="flex min-h-16 cursor-pointer items-center justify-center rounded-lg border border-dashed border-app-borde bg-app-fondo px-4 text-sm font-black text-app-texto-secundario transition hover:border-app-primario hover:text-app-primario">
          {isUploading ? "Subiendo imagen..." : "Subir una imagen de referencia"}
          <input className="sr-only" type="file" accept="image/*" onChange={handleImageUpload} />
        </label>
        {form.url_imagen ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-app-borde bg-app-fondo p-3">
            <p className="min-w-0 truncate text-sm font-bold text-app-texto-secundario">{form.url_imagen}</p>
            <div className="flex shrink-0 items-center gap-2">
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-black text-app-texto-primario transition hover:border-app-primario hover:text-app-primario"
                type="button"
                onClick={() => setPreviewImage(form.url_imagen)}
              >
                <EyeIcon />
                Ver imagen
              </button>
              <button
                className="h-10 rounded-lg border border-red-200 bg-red-50 px-3 text-sm font-black text-app-error transition hover:bg-red-100"
                type="button"
                onClick={() => {
                  updateField("url_imagen", "");
                  setError("Sube o ingresa una imagen de reemplazo antes de guardar la ruta.");
                }}
              >
                Quitar
              </button>
            </div>
          </div>
        ) : null}
        <FormField label="Descripción">
          <textarea
            className={`${formTextareaClass} min-h-24`}
            required
            value={form.descripcion}
            onChange={(event) => updateField("descripcion", event.target.value)}
          />
        </FormField>
        <ToggleRow checked={form.activo} onChange={(activo) => updateField("activo", activo)}>
          Ruta activa
        </ToggleRow>
      </AdminModal>
      {previewImage ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/90 p-4">
          <button
            className="absolute right-4 top-4 grid h-10 w-10 place-items-center rounded-lg bg-white/10 text-2xl font-black text-white transition hover:bg-white/20"
            type="button"
            onClick={() => setPreviewImage("")}
            aria-label="Cerrar imagen"
          >
            x
          </button>
          <img
            className="max-h-[86vh] max-w-[92vw] rounded-lg object-contain shadow-2xl"
            src={previewImage}
            alt="Imagen de referencia de la ruta"
          />
        </div>
      ) : null}
    </>
  );
}

function Pagination({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-app-borde px-4 py-3 text-sm">
      <p className="font-semibold text-app-texto-secundario">Mostrando {from}-{to} de {total} registros</p>
      <div className="flex items-center gap-2">
        <button className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario disabled:opacity-50" type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Anterior</button>
        <span className="grid h-9 min-w-9 place-items-center rounded-lg bg-app-primario px-3 text-sm font-black text-white">{page}</span>
        <button className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario disabled:opacity-50" type="button" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>Siguiente</button>
      </div>
    </div>
  );
}

export default function RoutesPage() {
  const sesion = obtenerSesion();
  const puedeCrear = tieneAccion(sesion, "routes", "crear");
  const puedeActualizar = tieneAccion(sesion, "routes", "actualizar");
  const puedeEliminar = tieneAccion(sesion, "routes", "eliminar");
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [filters, setFilters] = useState({ q: "", tipo_ruta: "", estado: "all", page: 1, page_size: 10 });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [geometryRoute, setGeometryRoute] = useState(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    let isActive = true;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await obtenerRutas(filters);
        if (isActive) setData(response);
      } catch (err) {
        if (isActive) setError(getApiErrorMessage(err, "No se pudo completar la operación"));
      } finally {
        if (isActive) setIsLoading(false);
      }
    }, 250);
    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [filters, refreshToken]);

  const typeOptions = useMemo(
    () => [{ value: "", label: "Tipo de ruta" }, ...routeTypes.map((type) => ({ value: type, label: type }))],
    [],
  );

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
  }

  function handleSaved() {
    setModal(null);
    setRefreshToken((current) => current + 1);
  }

  function requestDelete(route) {
    setConfirmAction({
      title: "Eliminar ruta",
      message: `Se eliminará la ruta ${route.titulo} y sus imágenes asociadas.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarRuta(route.id_ruta),
    });
  }

  function requestToggleStatus(route) {
    const nextActive = !route.activo;
    setConfirmAction({
      title: nextActive ? "Activar ruta" : "Desactivar ruta",
      message: `¿${nextActive ? "Activar" : "Desactivar"} la ruta ${route.titulo}?`,
      confirmLabel: nextActive ? "Activar" : "Desactivar",
      run: async () => cambiarEstadoRuta(route.id_ruta, nextActive),
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
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsConfirming(false);
    }
  }

  if (geometryRoute) {
    return (
      <RouteGeometryPage
        route={geometryRoute}
        onBack={() => {
          setGeometryRoute(null);
          setRefreshToken((current) => current + 1);
        }}
      />
    );
  }

  return (
    <div className="space-y-5">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <Panel>
        <div className="grid min-w-0 gap-3 border-b border-app-borde p-4 lg:grid-cols-[minmax(220px,1fr)_auto]">
          <SearchBox
            label="Buscar ruta turística"
            placeholder="Buscar ruta turística..."
            value={filters.q}
            onChange={(value) => updateFilter("q", value)}
          />
          <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 lg:flex lg:flex-wrap lg:items-center lg:justify-end">
            <SelectFilter icon label="Tipo de ruta" options={typeOptions} value={filters.tipo_ruta} onChange={(value) => updateFilter("tipo_ruta", value)} />
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
            {puedeCrear ? (
              <AdminActionButton icon={<PlusIcon />} variant="primary" onClick={() => setModal({ type: "create" })}>
                Nueva ruta
              </AdminActionButton>
            ) : null}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-app-fondo text-xs font-black uppercase text-app-texto-secundario">
              <tr>
                <th className="min-w-[360px] px-4 py-3">Título</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-borde">
              {isLoading ? (
                <tr><td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={4}>Cargando rutas...</td></tr>
              ) : data.items.length ? (
                data.items.map((route) => (
                  <tr key={route.id_ruta}>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-app-primario-claro text-app-primario"><RouteIcon /></span>
                        <div>
                          <p className="font-black text-app-texto-primario">{route.titulo}</p>
                          <p className="mt-1 text-xs font-semibold text-app-texto-secundario">RT-{String(route.id_ruta).padStart(2, "0")}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-semibold text-app-texto-secundario">{route.tipo_ruta}</td>
                    <td className="px-4 py-3">
                      {puedeActualizar ? (
                        <button type="button" onClick={() => requestToggleStatus(route)}>
                          <StatusBadge active={route.activo} />
                        </button>
                      ) : (
                        <StatusBadge active={route.activo} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {puedeActualizar ? (
                          <>
                            <TableActionButton icon={<EyeIcon />} onClick={() => setGeometryRoute(route)}>Geometría</TableActionButton>
                            <TableActionButton icon={<EditIcon />} onClick={() => setModal({ type: "edit", route })}>Editar</TableActionButton>
                          </>
                        ) : null}
                        {puedeEliminar ? (
                          <TableActionButton icon={<TrashIcon />} variant="danger" onClick={() => requestDelete(route)}>Eliminar</TableActionButton>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={4}>No hay rutas con los filtros seleccionados.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={(page) => setFilters((current) => ({ ...current, page }))} />
      </Panel>

      {modal?.type === "create" ? (
        <RouteFormModal onClose={() => setModal(null)} onSaved={handleSaved} />
      ) : null}
      {modal?.type === "edit" ? (
        <RouteFormModal route={modal.route} onClose={() => setModal(null)} onSaved={handleSaved} />
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
