import { useEffect, useMemo, useState } from "react";
import { getApiErrorMessage } from "../../core/api/errors";
import { SelectFilter, TableActionButton, TimedAlert } from "../../core/ui/AdminControls";
import ActionTypeBadge from "../../core/ui/ActionTypeBadge";
import AdminModal from "../../core/ui/AdminModal";
import JsonDiffView, { JsonSingleView } from "../../core/ui/JsonDiffView";
import Pagination from "../../core/ui/Pagination";
import Panel from "../../core/ui/Panel";
import SearchBox from "../../core/ui/SearchBox";
import UserAvatar from "../../core/ui/UserAvatar";
import { EyeIcon } from "../../core/ui/icons";
import {
  obtenerCatalogosRegistroAcciones,
  obtenerDetalleRegistroAccion,
  obtenerRegistroAcciones,
} from "./actionLogService";

const moduloOptions = [
  { value: "all", label: "Módulo" },
  { value: "attractions", label: "Atractivos turísticos" },
  { value: "categories", label: "Categorías" },
  { value: "routes", label: "Rutas" },
  { value: "noticias", label: "Noticias" },
  { value: "chatbot_content", label: "Contenido chatbots" },
  { value: "admin_accounts", label: "Cuentas administrativas" },
  { value: "sistema", label: "Sistema" },
];

const accionOptions = [
  { value: "all", label: "Tipo de acción" },
  { value: "creacion", label: "Creación" },
  { value: "edicion", label: "Edición" },
  { value: "actualizacion", label: "Actualización" },
  { value: "desactivacion", label: "Desactivación" },
  { value: "eliminacion", label: "Eliminación" },
];

const resultadoOptions = [
  { value: "all", label: "Resultado" },
  { value: "exitoso", label: "Exitoso" },
  { value: "fallido", label: "Fallido" },
];

function formatFecha(value) {
  if (!value) return "—";
  const fecha = new Date(value);
  const year = fecha.getFullYear();
  const month = String(fecha.getMonth() + 1).padStart(2, "0");
  const day = String(fecha.getDate()).padStart(2, "0");
  const hours = String(fecha.getHours()).padStart(2, "0");
  const minutes = String(fecha.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day} ${hours}:${minutes}`;
}

function DetailField({ label, children }) {
  return (
    <div>
      <p className="text-xs font-black uppercase tracking-wide text-app-texto-secundario">{label}</p>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function LoginDetail({ detalle }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <DetailField label="Resultado">
        <p className="text-sm font-black capitalize text-app-texto-primario">{detalle.resultado || "—"}</p>
      </DetailField>
      <DetailField label="Usuario">
        <p className="text-sm font-semibold text-app-texto-primario">{detalle.username || "—"}</p>
      </DetailField>
      <DetailField label="User agent">
        <p className="break-words text-sm font-semibold text-app-texto-primario">{detalle.user_agent || "—"}</p>
      </DetailField>
      <DetailField label="Detalle">
        <p className="text-sm font-semibold text-app-texto-primario">{detalle.detalle || "—"}</p>
      </DetailField>
    </div>
  );
}

function ActionDetailData({ detalle }) {
  if (detalle.accion_tipo === "creacion") {
    return <JsonSingleView title="Datos creados" value={detalle.datos_nuevos} tone="added" />;
  }
  if (detalle.accion_tipo === "eliminacion") {
    return <JsonSingleView title="Datos eliminados" value={detalle.datos_anteriores} tone="removed" />;
  }
  return <JsonDiffView previous={detalle.datos_anteriores} next={detalle.datos_nuevos} />;
}

function DetailModal({ idEvento, vista, onClose }) {
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;
    setIsLoading(true);
    setError("");
    obtenerDetalleRegistroAccion(idEvento, vista)
      .then((response) => {
        if (isActive) setDetalle(response);
      })
      .catch((err) => {
        if (isActive) setError(getApiErrorMessage(err, "No se pudo cargar el detalle"));
      })
      .finally(() => {
        if (isActive) setIsLoading(false);
      });
    return () => {
      isActive = false;
    };
  }, [idEvento, vista]);

  return (
    <AdminModal
      error={error}
      maxWidth="max-w-5xl"
      onClose={onClose}
      onDismissError={() => setError("")}
      onSubmit={(event) => {
        event.preventDefault();
        onClose();
      }}
      submitLabel="Cerrar"
      title="Detalle de acción"
    >
      {isLoading ? (
        <p className="text-sm font-semibold text-app-texto-secundario">Cargando detalle...</p>
      ) : detalle ? (
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <DetailField label="Administrador">
              <p className="text-sm font-black text-app-texto-primario">{detalle.administrador}</p>
            </DetailField>
            <DetailField label="Fecha y hora">
              <p className="text-sm font-semibold text-app-texto-primario">{formatFecha(detalle.fecha_modificacion)}</p>
            </DetailField>
            <DetailField label="Acción">
              <ActionTypeBadge accionTipo={detalle.accion_tipo} label={detalle.accion_label} />
            </DetailField>
            <DetailField label="Módulo">
              <p className="text-sm font-semibold text-app-texto-primario">{detalle.modulo_label}</p>
            </DetailField>
            <DetailField label="Dirección">
              <p className="text-sm font-semibold text-app-texto-primario">{detalle.direccion || "—"}</p>
            </DetailField>
            <DetailField label="Referencia">
              <p className="text-sm font-semibold text-app-texto-primario">{detalle.referencia || "—"}</p>
            </DetailField>
          </div>
          {vista === "inicios_sesion" ? <LoginDetail detalle={detalle} /> : <ActionDetailData detalle={detalle} />}
        </div>
      ) : null}
    </AdminModal>
  );
}

export default function ActionLogPage() {
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [catalogos, setCatalogos] = useState({ administradores: [], modulos: [] });
  const [filters, setFilters] = useState({
    vista: "acciones",
    q: "",
    usuario: "",
    modulo: "all",
    accion: "all",
    resultado: "all",
    fecha_inicio: "",
    fecha_fin: "",
    page: 1,
    page_size: 10,
  });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    obtenerCatalogosRegistroAcciones()
      .then(setCatalogos)
      .catch(() => {});
  }, []);

  useEffect(() => {
    let isActive = true;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await obtenerRegistroAcciones(filters);
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
  }, [filters]);

  const adminOptions = useMemo(
    () => [
      { value: "", label: "Administrador" },
      ...catalogos.administradores.map((username) => ({ value: username, label: username })),
    ],
    [catalogos.administradores],
  );

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value, page: 1 }));
  }

  function setVista(vista) {
    setSelectedId(null);
    setFilters((current) => ({
      ...current,
      vista,
      modulo: "all",
      accion: "all",
      resultado: "all",
      page: 1,
    }));
  }

  return (
    <div className="space-y-5">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>

      <Panel>
        <div className="flex gap-2 border-b border-app-borde p-4">
          {[
            { value: "acciones", label: "Acciones" },
            { value: "inicios_sesion", label: "Inicios de sesión" },
          ].map((option) => (
            <button
              key={option.value}
              type="button"
              className={`h-10 rounded-lg border px-4 text-sm font-black transition ${
                filters.vista === option.value
                  ? "border-app-primario bg-app-primario text-white"
                  : "border-app-borde bg-app-tarjeta text-app-texto-secundario hover:border-app-primario"
              }`}
              onClick={() => setVista(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-app-borde p-4">
          <div className="min-w-[240px] flex-1 sm:max-w-sm">
            <SearchBox
              label={filters.vista === "inicios_sesion" ? "Buscar inicios de sesión" : "Buscar acciones"}
              placeholder="Buscar por administrador, IP o datos..."
              value={filters.q}
              onChange={(value) => updateFilter("q", value)}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SelectFilter icon label="Administrador" options={adminOptions} value={filters.usuario} onChange={(value) => updateFilter("usuario", value)} />
            {filters.vista === "acciones" ? (
              <>
                <SelectFilter icon label="Módulo" options={moduloOptions} value={filters.modulo} onChange={(value) => updateFilter("modulo", value)} />
                <SelectFilter icon label="Tipo de acción" options={accionOptions} value={filters.accion} onChange={(value) => updateFilter("accion", value)} />
              </>
            ) : (
              <SelectFilter icon label="Resultado" options={resultadoOptions} value={filters.resultado} onChange={(value) => updateFilter("resultado", value)} />
            )}
            <input
              className="h-10 rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-semibold text-app-texto-primario outline-none transition focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
              type="date"
              value={filters.fecha_inicio}
              onChange={(event) => updateFilter("fecha_inicio", event.target.value)}
              aria-label="Fecha inicio"
            />
            <input
              className="h-10 rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-semibold text-app-texto-primario outline-none transition focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
              type="date"
              value={filters.fecha_fin}
              onChange={(event) => updateFilter("fecha_fin", event.target.value)}
              aria-label="Fecha fin"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-app-fondo text-xs font-black uppercase text-app-texto-secundario">
              <tr>
                <th className="min-w-[220px] px-4 py-3">Administrador</th>
                <th className="px-4 py-3">Acción</th>
                <th className="px-4 py-3">Módulo</th>
                <th className="min-w-[160px] px-4 py-3">Fecha y hora</th>
                <th className="min-w-[140px] px-4 py-3">Dirección</th>
                <th className="px-4 py-3 text-right">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-borde">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={6}>
                    {filters.vista === "inicios_sesion" ? "Cargando inicios de sesión..." : "Cargando registro de acciones..."}
                  </td>
                </tr>
              ) : data.items.length ? (
                data.items.map((item) => (
                  <tr key={item.id_evento} className="align-middle">
                    <td className="px-4 py-3">
                      <UserAvatar initials={item.iniciales} name={item.administrador} />
                    </td>
                    <td className="px-4 py-3">
                      <ActionTypeBadge accionTipo={item.accion_tipo} label={item.accion_label} />
                    </td>
                    <td className="px-4 py-3 font-semibold text-app-texto-secundario">{item.modulo_label}</td>
                    <td className="px-4 py-3 font-semibold text-app-texto-secundario">{formatFecha(item.fecha_modificacion)}</td>
                    <td className="px-4 py-3 font-semibold text-app-texto-primario">{item.direccion || "—"}</td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end">
                        <TableActionButton icon={<EyeIcon />} onClick={() => setSelectedId(item.id_evento)}>
                          Ver
                        </TableActionButton>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={6}>
                    {filters.vista === "inicios_sesion" ? "No hay inicios de sesión con los filtros seleccionados." : "No hay acciones con los filtros seleccionados."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <Pagination
          page={data.page}
          pageSize={data.page_size}
          total={data.total}
          onPageChange={(page) => setFilters((current) => ({ ...current, page }))}
        />
      </Panel>

      {selectedId ? <DetailModal idEvento={selectedId} vista={filters.vista} onClose={() => setSelectedId(null)} /> : null}
    </div>
  );
}
