/**
 * Barra superior estándar para vistas con búsqueda, filtros y acciones.
 * Patrón: búsqueda a la izquierda (ancho máx. compacto), controles a la derecha.
 */
import { text } from "../typography";

export default function PanelToolbar({ actions = null, filters = null, meta = null, search = null }) {
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-app-borde p-4">
        {search ? (
          <div className="w-full min-w-0 flex-1 sm:min-w-[220px] lg:max-w-xs">{search}</div>
        ) : (
          <div className="min-w-0 flex-1" />
        )}
        {filters || actions ? (
          <div className="grid w-full min-w-0 grid-cols-1 gap-2 sm:flex sm:w-auto sm:flex-wrap sm:items-center sm:justify-end">
            {filters}
            {actions}
          </div>
        ) : null}
      </div>
      {meta ? (
        <div className={`border-b border-app-borde bg-app-fondo/60 px-4 py-2.5 ${text.panelMeta}`}>
          {meta}
        </div>
      ) : null}
    </>
  );
}
