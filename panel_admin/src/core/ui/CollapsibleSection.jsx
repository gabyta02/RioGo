import { ChevronDownIcon } from "./icons";

export default function CollapsibleSection({
  children,
  description,
  expanded = false,
  onToggle,
  title,
}) {
  return (
    <section className="overflow-hidden rounded-lg border border-app-borde bg-app-tarjeta">
      <button
        className="flex w-full items-center gap-3 px-4 py-4 text-left transition hover:bg-app-fondo"
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span
          className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-app-borde bg-app-tarjeta text-app-texto-secundario ${
            expanded ? "border-app-primario bg-app-primario-claro text-app-primario" : ""
          }`}
          aria-hidden="true"
        >
          <ChevronDownIcon
            className={`h-5 w-5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
          />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-black text-app-texto-primario">{title}</p>
          {description ? (
            <p className="mt-1 text-xs font-semibold text-app-texto-secundario">{description}</p>
          ) : null}
        </div>
      </button>
      {expanded ? (
        <div className="border-t border-app-borde bg-app-fondo px-4 py-4">
          {children}
        </div>
      ) : null}
    </section>
  );
}
