import { useEffect, useMemo, useState } from "react";
import SearchBox from "../../core/ui/SearchBox";
import { AdminActionButton, TableActionButton } from "../../core/ui/AdminControls";
import { getApiErrorMessage } from "../../core/api/errors";
import { obtenerCatalogoSitiosCuenta } from "./adminAccountsService";
import PermisosSitioInfoModal from "./PermisosSitioInfoModal";

function SiteStatusBadge({ active }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-black ${
        active ? "bg-emerald-50 text-app-primario" : "bg-app-fondo text-app-texto-secundario"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${active ? "bg-app-primario" : "bg-app-borde"}`} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function formatCategoria(sitio) {
  if (sitio.subcategoria) {
    return `${sitio.categoria} / ${sitio.subcategoria}`;
  }
  return sitio.categoria || "—";
}

export default function SitiosAsignadosSection({
  error = "",
  onChange,
  requerido = false,
  sitiosAsignados,
  sitiosAsignadosDetalleInicial = [],
}) {
  const [busqueda, setBusqueda] = useState("");
  const [catalogo, setCatalogo] = useState([]);
  const [sitiosDetalle, setSitiosDetalle] = useState(() =>
    Object.fromEntries(sitiosAsignadosDetalleInicial.map((sitio) => [sitio.id_sitio, sitio])),
  );
  const [isLoadingCatalogo, setIsLoadingCatalogo] = useState(true);
  const [catalogoError, setCatalogoError] = useState("");
  const [sitioPermisos, setSitioPermisos] = useState(null);

  useEffect(() => {
    setSitiosDetalle((current) => {
      const next = { ...current };
      for (const sitio of sitiosAsignadosDetalleInicial) {
        next[sitio.id_sitio] = sitio;
      }
      return next;
    });
  }, [sitiosAsignadosDetalleInicial]);

  useEffect(() => {
    let isActive = true;
    const timer = window.setTimeout(async () => {
      setIsLoadingCatalogo(true);
      setCatalogoError("");
      try {
        const response = await obtenerCatalogoSitiosCuenta({
          estado: "activo",
          page: 1,
          page_size: 100,
          q: busqueda.trim() || undefined,
        });
        if (!isActive) return;

        let items = response.items || [];
        if (response.total > items.length) {
          const paginas = Math.ceil(response.total / 100);
          const requests = [];
          for (let page = 2; page <= paginas; page += 1) {
            requests.push(
              obtenerCatalogoSitiosCuenta({
                estado: "activo",
                page,
                page_size: 100,
                q: busqueda.trim() || undefined,
              }),
            );
          }
          const extra = await Promise.all(requests);
          items = items.concat(...extra.map((result) => result.items || []));
        }

        setCatalogo(items);
      } catch (err) {
        if (!isActive) return;
        setCatalogo([]);
        setCatalogoError(getApiErrorMessage(err, "No se pudo cargar el catálogo de sitios."));
      } finally {
        if (isActive) {
          setIsLoadingCatalogo(false);
        }
      }
    }, 250);

    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [busqueda]);

  const sitiosAsignadosSet = useMemo(() => new Set(sitiosAsignados), [sitiosAsignados]);

  const sitiosAsignadosDetalle = useMemo(
    () =>
      sitiosAsignados.map((idSitio) => {
        const sitio = sitiosDetalle[idSitio] || catalogo.find((item) => item.id_sitio === idSitio);
        if (sitio) {
          return sitio;
        }
        return {
          id_sitio: idSitio,
          nombre: `Sitio #${idSitio}`,
          categoria: "—",
          subcategoria: null,
          activo: true,
        };
      }),
    [catalogo, sitiosAsignados, sitiosDetalle],
  );

  const sitiosDisponibles = useMemo(
    () => catalogo.filter((sitio) => !sitiosAsignadosSet.has(sitio.id_sitio)),
    [catalogo, sitiosAsignadosSet],
  );

  function agregarSitio(sitio) {
    if (sitiosAsignadosSet.has(sitio.id_sitio)) {
      return;
    }
    setSitiosDetalle((current) => ({ ...current, [sitio.id_sitio]: sitio }));
    onChange([...sitiosAsignados, sitio.id_sitio]);
  }

  function quitarSitio(idSitio) {
    onChange(sitiosAsignados.filter((id) => id !== idSitio));
  }

  return (
    <div className="space-y-4 rounded-lg border border-app-borde bg-app-fondo/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-black text-app-texto-primario">
            Sitios asignados
            {requerido ? <span className="text-app-error"> *</span> : null}
          </p>
          <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
            {requerido
              ? "Obligatorio: asigna al menos un atractivo activo que este dueño podrá administrar."
              : "Atractivos bajo administración de este dueño."}
          </p>
        </div>
        <span className="inline-flex items-center rounded-full bg-app-primario-claro px-3 py-1 text-xs font-black text-app-primario">
          Alcance: solo sitios asignados
        </span>
      </div>

      <SearchBox
        label="Buscar sitio turístico"
        placeholder="Buscar por nombre..."
        value={busqueda}
        onChange={setBusqueda}
      />

      {catalogoError ? (
        <p className="rounded-lg border border-app-error-borde bg-app-error-fondo px-3 py-2 text-sm font-semibold text-app-error">
          {catalogoError}
        </p>
      ) : null}

      {isLoadingCatalogo ? (
        <p className="text-sm font-semibold text-app-texto-secundario">Buscando sitios activos...</p>
      ) : sitiosDisponibles.length ? (
        <div className="max-h-36 space-y-2 overflow-y-auto rounded-lg border border-app-borde bg-app-tarjeta p-3">
          {sitiosDisponibles.map((sitio) => (
            <div
              key={sitio.id_sitio}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-app-borde px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-black text-app-texto-primario">{sitio.nombre}</p>
                <p className="text-xs font-semibold text-app-texto-secundario">{formatCategoria(sitio)}</p>
              </div>
              <AdminActionButton type="button" variant="secondary" onClick={() => agregarSitio(sitio)}>
                Agregar
              </AdminActionButton>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm font-semibold text-app-texto-secundario">
          {catalogoError
            ? "No se pudo cargar el catálogo de sitios."
            : busqueda.trim()
              ? "No hay sitios activos que coincidan con la búsqueda."
              : "No hay más sitios activos disponibles para asignar."}
        </p>
      )}

      {sitiosAsignadosDetalle.length ? (
        <div className="overflow-x-auto rounded-lg border border-app-borde bg-app-tarjeta">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-app-fondo text-xs font-black uppercase text-app-texto-secundario">
              <tr>
                <th className="px-3 py-2">Nombre</th>
                <th className="px-3 py-2">Categoría</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-borde">
              {sitiosAsignadosDetalle.map((sitio) => (
                <tr key={sitio.id_sitio}>
                  <td className="px-3 py-2 font-black text-app-texto-primario">{sitio.nombre}</td>
                  <td className="px-3 py-2 font-semibold text-app-texto-secundario">
                    {formatCategoria(sitio)}
                  </td>
                  <td className="px-3 py-2">
                    <SiteStatusBadge active={sitio.activo} />
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex justify-end gap-2">
                      <TableActionButton onClick={() => setSitioPermisos(sitio)}>
                        Ver permisos
                      </TableActionButton>
                      <TableActionButton variant="danger" onClick={() => quitarSitio(sitio.id_sitio)}>
                        Quitar
                      </TableActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p
          className={`rounded-lg border px-4 py-6 text-center text-sm font-semibold ${
            error
              ? "border-app-error-borde bg-app-error-fondo text-app-error"
              : "border-dashed border-app-borde text-app-texto-secundario"
          }`}
        >
          {error ||
            (requerido
              ? "Debes asignar al menos un sitio. Busca un atractivo activo y haz clic en Agregar."
              : "Aún no hay sitios asignados. Busca y agrega los atractivos que este dueño podrá administrar.")}
        </p>
      )}

      {sitioPermisos ? (
        <PermisosSitioInfoModal sitio={sitioPermisos} onClose={() => setSitioPermisos(null)} />
      ) : null}
    </div>
  );
}
