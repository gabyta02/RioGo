import { useEffect, useState } from "react";
import { getApiErrorMessage } from "../../core/api/errors";
import {
  AdminActionButton,
  FormField,
  TableActionButton,
  TimedAlert,
  ToggleRow,
  formInputClass,
} from "../../core/ui/AdminControls";
import AdminModal from "../../core/ui/AdminModal";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import Panel from "../../core/ui/Panel";
import { EditIcon, EyeIcon, PlusIcon, TrashIcon } from "../../core/ui/icons";
import { obtenerSesion, tieneAccion } from "../../core/auth/authStorage";
import {
  actualizarNoticia,
  cambiarEstadoNoticia,
  crearNoticia,
  eliminarNoticia,
  obtenerNoticias,
  subirImagenNoticia,
} from "./noticiasService";

const logoSrc = `${import.meta.env.BASE_URL}assets/logo.png`;

function CalendarIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3M5 11h14M6 21h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2Z" />
    </svg>
  );
}

const statusStyles = {
  publicada: {
    label: "Publicada",
    dot: "bg-app-exito",
    badge: "border-emerald-200 bg-emerald-50 text-app-primario",
  },
  vencida: {
    label: "Vencida",
    dot: "bg-app-error",
    badge: "border-red-200 bg-red-50 text-app-error",
  },
  inactiva: {
    label: "Inactiva",
    dot: "bg-app-texto-secundario",
    badge: "border-slate-200 bg-slate-100 text-app-texto-secundario",
  },
};

function formatDate(value) {
  return value || "—";
}

function NewsStatusBadge({ estadoVisual, onClick }) {
  const style = statusStyles[estadoVisual] || statusStyles.inactiva;
  const content = (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-black ${style.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${style.dot}`} />
      {style.label}
    </span>
  );

  if (!onClick) {
    return content;
  }

  return (
    <button className="rounded-full transition hover:opacity-80" type="button" onClick={onClick}>
      {content}
    </button>
  );
}

function NewsCard({ noticia, onEdit, onToggleStatus }) {
  return (
    <article className="flex h-full flex-col overflow-hidden rounded-xl border border-app-borde bg-app-tarjeta shadow-sm">
      <div className="relative aspect-[16/10] bg-app-primario-claro">
        <img
          className="h-full w-full object-cover"
          src={noticia.imagen_url || logoSrc}
          alt={noticia.titulo}
        />
        <div className="absolute left-3 top-3">
          <NewsStatusBadge
            estadoVisual={noticia.estado_visual}
            onClick={onToggleStatus ? () => onToggleStatus(noticia) : undefined}
          />
        </div>
      </div>
      <div className="flex flex-1 flex-col p-4">
        <h3 className="line-clamp-2 text-base font-black text-app-texto-primario">{noticia.titulo}</h3>
        <div className="mt-4 space-y-2 text-sm font-semibold text-app-texto-secundario">
          <p className="flex items-center gap-2">
            <CalendarIcon />
            <span>
              Fecha de inicio: <span className="text-app-texto-primario">{formatDate(noticia.fecha_inicio)}</span>
            </span>
          </p>
          <p className="flex items-center gap-2">
            <CalendarIcon />
            <span>
              Fecha de fin: <span className="text-app-texto-primario">{formatDate(noticia.fecha_fin)}</span>
            </span>
          </p>
        </div>
        {onEdit ? (
          <div className="mt-4">
            <TableActionButton icon={<EditIcon />} onClick={() => onEdit(noticia)}>
              Editar
            </TableActionButton>
          </div>
        ) : null}
      </div>
    </article>
  );
}

function NoticiaFormModal({ noticia, onClose, onDelete, onSaved }) {
  const isEdit = Boolean(noticia);
  const [form, setForm] = useState({
    titulo: noticia?.titulo || "",
    imagen_url: noticia?.imagen_url || "",
    fecha_inicio: noticia?.fecha_inicio || "",
    fecha_fin: noticia?.fecha_fin || "",
    activa: noticia?.activa ?? true,
  });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [previewImage, setPreviewImage] = useState("");

  function updateField(key, value) {
    setError("");
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.titulo.trim()) {
      setError("Ingresa el título de la noticia");
      return;
    }
    if (!form.fecha_inicio) {
      setError("Ingresa la fecha de inicio");
      return;
    }
    if (form.fecha_fin && form.fecha_fin < form.fecha_inicio) {
      setError("La fecha de fin debe ser mayor o igual a la fecha de inicio");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const payload = {
        titulo: form.titulo.trim(),
        imagen_url: form.imagen_url.trim() || null,
        fecha_inicio: form.fecha_inicio,
        fecha_fin: form.fecha_fin || null,
        activa: form.activa,
      };

      if (!isEdit) {
        await crearNoticia(payload);
      } else {
        await actualizarNoticia(noticia.id_noticia, payload);
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
      setError("Primero ingresa el título de la noticia para subir la imagen");
      return;
    }
    setIsUploading(true);
    setError("");
    try {
      const uploaded = await subirImagenNoticia(form.titulo.trim(), file);
      updateField("imagen_url", uploaded.url);
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
        submitLabel={isEdit ? "Guardar noticia" : "Crear noticia"}
        title={isEdit ? "Editar noticia" : "Nueva noticia"}
        maxWidth="max-w-2xl"
      >
        <FormField label="Título">
          <input
            className={formInputClass}
            maxLength={200}
            required
            value={form.titulo}
            onChange={(event) => updateField("titulo", event.target.value)}
          />
        </FormField>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Fecha de inicio">
            <input
              className={formInputClass}
              required
              type="date"
              value={form.fecha_inicio}
              onChange={(event) => updateField("fecha_inicio", event.target.value)}
            />
          </FormField>
          <FormField label="Fecha de fin">
            <input
              className={formInputClass}
              type="date"
              value={form.fecha_fin}
              onChange={(event) => updateField("fecha_fin", event.target.value)}
            />
          </FormField>
        </div>
        <FormField label="Imagen URL">
          <input
            className={formInputClass}
            placeholder="/api/v1/imagenes/noticias/titulo/imagen.jpg"
            value={form.imagen_url}
            onChange={(event) => updateField("imagen_url", event.target.value)}
          />
        </FormField>
        <label className="flex min-h-16 cursor-pointer items-center justify-center rounded-lg border border-dashed border-app-borde bg-app-fondo px-4 text-sm font-black text-app-texto-secundario transition hover:border-app-primario hover:text-app-primario">
          {isUploading ? "Subiendo imagen..." : "Subir imagen de la noticia"}
          <input className="sr-only" type="file" accept="image/*" onChange={handleImageUpload} />
        </label>
        {form.imagen_url ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-app-borde bg-app-fondo p-3">
            <p className="min-w-0 truncate text-sm font-bold text-app-texto-secundario">{form.imagen_url}</p>
            <div className="flex shrink-0 items-center gap-2">
              <button
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-black text-app-texto-primario transition hover:border-app-primario hover:text-app-primario"
                type="button"
                onClick={() => setPreviewImage(form.imagen_url)}
              >
                <EyeIcon />
                Ver imagen
              </button>
              <button
                className="h-10 rounded-lg border border-red-200 bg-red-50 px-3 text-sm font-black text-app-error transition hover:bg-red-100"
                type="button"
                onClick={() => updateField("imagen_url", "")}
              >
                Quitar
              </button>
            </div>
          </div>
        ) : null}
        <ToggleRow checked={form.activa} onChange={(activa) => updateField("activa", activa)}>
          Noticia activa
        </ToggleRow>
        {isEdit && onDelete ? (
          <div className="flex justify-end border-t border-app-borde pt-4">
            <TableActionButton icon={<TrashIcon />} variant="danger" onClick={() => onDelete(noticia)}>
              Eliminar noticia
            </TableActionButton>
          </div>
        ) : null}
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
            alt="Imagen de la noticia"
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

export default function NoticiasPage() {
  const sesion = obtenerSesion();
  const puedeCrear = tieneAccion(sesion, "noticias", "crear");
  const puedeActualizar = tieneAccion(sesion, "noticias", "actualizar");
  const puedeEliminar = tieneAccion(sesion, "noticias", "eliminar");
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 12 });
  const [filters, setFilters] = useState({ q: "", estado: "all", page: 1, page_size: 12 });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [modal, setModal] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [isConfirming, setIsConfirming] = useState(false);

  useEffect(() => {
    let isActive = true;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await obtenerNoticias(filters);
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

  function handleSaved() {
    setModal(null);
    setRefreshToken((current) => current + 1);
  }

  function requestDelete(noticia) {
    setModal(null);
    setConfirmAction({
      title: "Eliminar noticia",
      message: `Se eliminará la noticia ${noticia.titulo} y su imagen asociada.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarNoticia(noticia.id_noticia),
    });
  }

  function requestToggleStatus(noticia) {
    const nextActive = !noticia.activa;
    setConfirmAction({
      title: nextActive ? "Activar noticia" : "Desactivar noticia",
      message: `¿${nextActive ? "Activar" : "Desactivar"} la noticia ${noticia.titulo}?`,
      confirmLabel: nextActive ? "Activar" : "Desactivar",
      run: async () => cambiarEstadoNoticia(noticia.id_noticia, nextActive),
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

  return (
    <div className="space-y-5">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm font-semibold text-app-texto-secundario">
          {data.total} {data.total === 1 ? "noticia registrada" : "noticias registradas"}
        </p>
        {puedeCrear ? (
          <AdminActionButton icon={<PlusIcon />} variant="primary" onClick={() => setModal({ type: "create" })}>
            Nueva noticia
          </AdminActionButton>
        ) : null}
      </div>

      {isLoading ? (
        <Panel className="p-8 text-center text-sm font-semibold text-app-texto-secundario">
          Cargando noticias...
        </Panel>
      ) : data.items.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {data.items.map((noticia) => (
            <NewsCard
              key={noticia.id_noticia}
              noticia={noticia}
              onEdit={puedeActualizar ? (item) => setModal({ type: "edit", noticia: item }) : undefined}
              onToggleStatus={puedeActualizar ? requestToggleStatus : undefined}
            />
          ))}
        </div>
      ) : (
        <Panel className="p-8 text-center">
          <p className="text-sm font-semibold text-app-texto-secundario">
            No hay noticias registradas.
          </p>
          <div className="mt-4">
            {puedeCrear ? (
              <AdminActionButton icon={<PlusIcon />} variant="primary" onClick={() => setModal({ type: "create" })}>
                Nueva noticia
              </AdminActionButton>
            ) : null}
          </div>
        </Panel>
      )}

      {data.total > data.page_size ? (
        <Panel>
          <Pagination
            page={data.page}
            pageSize={data.page_size}
            total={data.total}
            onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
          />
        </Panel>
      ) : null}

      {modal?.type === "create" ? (
        <NoticiaFormModal onClose={() => setModal(null)} onSaved={handleSaved} />
      ) : null}
      {modal?.type === "edit" ? (
        <NoticiaFormModal
          noticia={modal.noticia}
          onClose={() => setModal(null)}
          onDelete={puedeEliminar ? requestDelete : undefined}
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
