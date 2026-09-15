import { PERMISOS_POR_SITIO_INFO } from "./duenoPermissions";

export default function PermisosSitioInfoModal({ sitio, onClose }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center overflow-y-auto bg-slate-900/30 p-4">
      <div className="w-full max-w-lg overflow-hidden rounded-lg bg-app-tarjeta shadow-2xl">
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h2 className="text-lg font-black text-app-texto-primario">Permisos del sitio</h2>
            <p className="mt-1 text-sm font-semibold text-app-texto-secundario">
              {sitio?.nombre || "Sitio asignado"}
            </p>
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
          <p className="text-sm font-semibold text-app-texto-secundario">
            Al asignar un sitio a un dueño, el sistema aplica automáticamente estos permisos
            con alcance exclusivo sobre ese atractivo.
          </p>

          {PERMISOS_POR_SITIO_INFO.map((grupo) => (
            <div key={grupo.modulo} className="rounded-lg border border-app-borde p-4">
              <p className="text-sm font-black text-app-texto-primario">{grupo.modulo}</p>
              <ul className="mt-2 space-y-1">
                {grupo.permisos.map((permiso) => (
                  <li
                    key={permiso}
                    className="flex items-start gap-2 text-sm font-semibold text-app-texto-secundario"
                  >
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-app-primario" />
                    {permiso}
                  </li>
                ))}
              </ul>
            </div>
          ))}

          <p className="rounded-lg bg-app-fondo px-3 py-2 text-xs font-semibold text-app-texto-secundario">
            La personalización de permisos por sitio estará disponible en una próxima versión.
          </p>
        </div>

        <div className="flex justify-end border-t border-app-borde bg-app-fondo px-5 py-4">
          <button
            className="inline-flex h-10 items-center justify-center rounded-lg border border-app-borde bg-app-tarjeta px-4 text-sm font-black text-app-texto-primario transition hover:border-app-primario hover:text-app-primario"
            type="button"
            onClick={onClose}
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
