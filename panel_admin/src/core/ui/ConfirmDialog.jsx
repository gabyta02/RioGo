import { AdminActionButton } from "./AdminControls";

export default function ConfirmDialog({
  confirmLabel = "Confirmar",
  isLoading = false,
  message,
  onCancel,
  onConfirm,
  title,
  variant = "danger",
}) {
  const confirmVariant = variant === "danger" ? "primary" : "primary";

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md overflow-hidden rounded-lg bg-app-tarjeta shadow-2xl">
        <div className="px-5 pt-5">
          <h2 className="text-lg font-black text-app-texto-primario">{title}</h2>
          <p className="mt-2 text-sm font-semibold leading-6 text-app-texto-secundario">{message}</p>
        </div>
        <div className="mt-5 flex justify-end gap-3 border-t border-app-borde bg-app-fondo px-5 py-4">
          <AdminActionButton disabled={isLoading} onClick={onCancel}>Cancelar</AdminActionButton>
          <AdminActionButton disabled={isLoading} variant={confirmVariant} onClick={onConfirm}>
            {isLoading ? "Procesando..." : confirmLabel}
          </AdminActionButton>
        </div>
      </div>
    </div>
  );
}
