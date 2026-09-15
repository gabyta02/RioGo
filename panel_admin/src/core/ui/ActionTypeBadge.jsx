const actionStyles = {
  creacion: "border-app-exito-borde bg-app-exito-fondo text-app-primario",
  edicion: "border-blue-200 bg-blue-50 text-blue-700",
  actualizacion: "border-orange-200 bg-orange-50 text-orange-700",
  desactivacion: "border-app-error-borde bg-app-error-fondo text-app-error",
  eliminacion: "border-app-error-borde bg-app-error-fondo text-app-error",
  sesion: "border-slate-200 bg-slate-100 text-app-texto-secundario",
  otro: "border-slate-200 bg-slate-100 text-app-texto-secundario",
};

const actionDots = {
  creacion: "bg-app-exito",
  edicion: "bg-blue-500",
  actualizacion: "bg-app-acento",
  desactivacion: "bg-app-error",
  eliminacion: "bg-app-error",
  sesion: "bg-app-texto-secundario",
  otro: "bg-app-texto-secundario",
};

export default function ActionTypeBadge({ accionTipo, label }) {
  const style = actionStyles[accionTipo] || actionStyles.otro;
  const dot = actionDots[accionTipo] || actionDots.otro;

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black ${style}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
