export default function EntityStatusBadge({ active, children }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-black ${
        active
          ? "border-app-exito-borde bg-app-exito-fondo text-app-primario"
          : "border-slate-200 bg-slate-100 text-app-texto-secundario"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-app-exito" : "bg-app-texto-secundario"}`} />
      {children || (active ? "Activo" : "Inactivo")}
    </span>
  );
}
