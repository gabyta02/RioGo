import { AdminActionButton, TimedAlert } from "./AdminControls";

export default function AdminModal({
  children,
  error = "",
  isSaving = false,
  maxWidth = "max-w-lg",
  onClose,
  onDismissError,
  onSubmit,
  submitLabel = "Guardar",
  title,
  subtitle,
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/30 p-4">
      <form
        className={`w-full ${maxWidth} overflow-hidden rounded-lg bg-app-tarjeta shadow-2xl`}
        onSubmit={onSubmit}
      >
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h2 className="text-lg font-black text-app-texto-primario">{title}</h2>
            {subtitle ? (
              <p className="mt-1 text-sm font-semibold text-app-texto-secundario">
                {subtitle}
              </p>
            ) : null}
          </div>
          <button
            className="grid h-8 w-8 place-items-center rounded-lg text-xl leading-none text-app-texto-primario transition hover:bg-app-fondo"
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
          >
            x
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <TimedAlert onDismiss={onDismissError}>{error}</TimedAlert>
          {children}
        </div>

        <div className="flex justify-end gap-3 border-t border-app-borde bg-app-fondo px-5 py-4">
          <AdminActionButton onClick={onClose}>Cancelar</AdminActionButton>
          <AdminActionButton variant="primary" type="submit" disabled={isSaving}>
            {isSaving ? "Guardando..." : submitLabel}
          </AdminActionButton>
        </div>
      </form>
    </div>
  );
}
