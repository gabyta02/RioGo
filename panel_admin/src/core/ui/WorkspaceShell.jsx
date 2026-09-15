import { text } from "../typography";

export default function WorkspaceShell({
  actions = null,
  children,
  onBack,
  subtitle,
  title,
}) {
  return (
    <div className="flex min-h-[calc(100dvh-7.5rem)] flex-col gap-3 xl:h-[calc(100dvh-7.5rem)] xl:min-h-[520px]">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <button
            className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-app-borde bg-app-tarjeta text-lg font-black text-app-primario transition hover:border-app-primario hover:bg-app-primario-claro"
            type="button"
            onClick={onBack}
            aria-label="Volver"
          >
            ←
          </button>
          <div className="min-w-0">
            <h2 className={`truncate ${text.entityTitle}`}>{title}</h2>
            {subtitle ? <p className={`mt-0.5 truncate ${text.entityMeta}`}>{subtitle}</p> : null}
          </div>
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </header>
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-app-borde bg-app-tarjeta">
        {children}
      </div>
    </div>
  );
}

export function WorkspaceSidebar({ children, className = "", title }) {
  return (
    <aside className={`flex min-h-0 min-w-0 flex-col border-app-borde bg-app-fondo ${className}`}>
      {title ? (
        <div className="shrink-0 border-b border-app-borde p-4">
          <h3 className={text.entityTitle}>{title}</h3>
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1 flex-col p-4">{children}</div>
    </aside>
  );
}
