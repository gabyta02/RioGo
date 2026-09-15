import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Panel from "../../core/ui/Panel";
import PanelHeader from "../../core/ui/PanelHeader";
import StatCard from "../../core/ui/StatCard";
import { DashboardDateFilters } from "../../core/ui/AdminControls";
import {
  ChartIcon,
  ContentIcon,
  MapPinIcon,
  NewsIcon,
  RouteIcon,
  UserIcon,
} from "../../core/ui/icons";
import { obtenerDashboardInicial } from "./dashboardService";
import { getApiErrorMessage } from "../../core/api/errors";
import { esDuenoSitio, obtenerSesion, sinSitiosAsignados, tieneAlcanceSitio } from "../../core/auth/authStorage";
import OwnerDashboardPage from "./OwnerDashboardPage";

const GLOBAL_STAT_KEYS = new Set(["usuarios_registrados", "noticias_activas", "rutas_activas"]);

const CHATBOT_COLORS = {
  general: "#00876F",
  sitio: "#E98232",
};

const USER_COLORS = {
  usuario_movil: "#00876F",
  dueno: "#E98232",
  admin: "#2563EB",
  super_admin: "#7C3AED",
};

const statDefinitions = [
  {
    key: "atractivos_activos",
    label: "Atractivos activos",
    icon: <MapPinIcon />,
  },
  {
    key: "preguntas_chatbots",
    label: "Preguntas a chatbots",
    icon: <ContentIcon />,
  },
  {
    key: "favoritos_guardados",
    label: "Favoritos guardados",
    icon: <ChartIcon />,
  },
  {
    key: "noticias_activas",
    label: "Noticias activas",
    icon: <NewsIcon />,
  },
  {
    key: "rutas_activas",
    label: "Rutas activas",
    icon: <RouteIcon />,
  },
];

function formatNumber(value = 0) {
  return new Intl.NumberFormat("es-EC").format(value);
}

function EmptyState({ label = "Sin datos disponibles" }) {
  return (
    <div className="grid h-full min-h-[180px] place-items-center rounded-lg border border-dashed border-app-borde bg-app-fondo text-sm font-semibold text-app-texto-secundario">
      {label}
    </div>
  );
}

function mapQuestionSeries(response) {
  const byLabel = new Map();

  response?.series?.forEach((serie) => {
    serie.data.forEach((point) => {
      const current = byLabel.get(point.label) || { day: point.label };
      current[serie.key] = point.valor;
      byLabel.set(point.label, current);
    });
  });

  return Array.from(byLabel.values());
}

function mapPieItems(response) {
  return (response?.items || []).map((item) => ({
    name: item.label === "general" ? "Chatbot general" : item.label === "sitio" ? "Chatbot por sitio" : item.label,
    key: item.key,
    value: item.valor,
    color: CHATBOT_COLORS[item.key] || "#0D5A38",
  }));
}

function mapUserItems(response) {
  return (response?.items || []).map((item) => ({
    name: item.label,
    key: item.key,
    value: item.valor,
    color: USER_COLORS[item.key] || "#0D5A38",
  }));
}

function mapCategoryItems(response) {
  return (response?.items || []).map((item) => ({
    name: item.label,
    value: item.valor,
  }));
}

function RankingList({ accent = "#00876F", items }) {
  if (!items.length) {
    return <EmptyState />;
  }

  const max = Math.max(...items.map((item) => item.valor), 1);

  return (
    <ol className="mt-6 space-y-4">
      {items.map((item) => (
        <li key={`${item.posicion}-${item.nombre}`}>
          <div className="flex items-center justify-between gap-4 text-sm">
            <div className="flex min-w-0 items-center gap-2">
              <span className="grid h-5 w-5 shrink-0 place-items-center rounded-full bg-app-primario-claro text-xs font-black text-app-primario">
                {item.posicion}
              </span>
              <span className="truncate font-bold text-app-texto-primario">{item.nombre}</span>
            </div>
            <span className="shrink-0 font-black text-app-texto-primario">
              {formatNumber(item.valor)}
            </span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-app-primario-claro">
            <div
              className="h-1.5 rounded-full"
              style={{ width: `${(item.valor / max) * 100}%`, backgroundColor: accent }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}

function AdminDashboardContent({ sesion }) {
  const alcanceSitio = tieneAlcanceSitio(sesion);
  const sinSitios = sinSitiosAsignados(sesion);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    periodo: "month",
    fecha_inicio: "",
    fecha_fin: "",
  });
  const [appliedFilters, setAppliedFilters] = useState(filters);
  const [isLoading, setIsLoading] = useState(true);

  const visibleStats = useMemo(
    () => statDefinitions.filter((stat) => !alcanceSitio || !GLOBAL_STAT_KEYS.has(stat.key)),
    [alcanceSitio],
  );

  useEffect(() => {
    if (sinSitios) {
      setDashboard(null);
      setError("");
      setIsLoading(false);
      return undefined;
    }

    let isActive = true;

    async function loadDashboard() {
      setIsLoading(true);
      setError("");

      try {
        const data = await obtenerDashboardInicial(appliedFilters);
        if (isActive) {
          setDashboard(data);
        }
      } catch (err) {
        if (isActive) {
          setError(getApiErrorMessage(err, "No se pudo cargar el dashboard"));
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      isActive = false;
    };
  }, [appliedFilters, sinSitios]);

  function handleApplyFilters() {
    if (filters.periodo === "custom") {
      if (!filters.fecha_inicio || !filters.fecha_fin) {
        setError("Selecciona la fecha de inicio y la fecha de fin.");
        return;
      }
      if (filters.fecha_fin < filters.fecha_inicio) {
        setError("La fecha de fin debe ser mayor o igual a la fecha de inicio.");
        return;
      }
    }

    setAppliedFilters(filters);
  }

  function handleClearFilters() {
    const defaultFilters = {
      periodo: "month",
      fecha_inicio: "",
      fecha_fin: "",
    };
    setFilters(defaultFilters);
    setAppliedFilters(defaultFilters);
  }

  const questionData = useMemo(
    () => mapQuestionSeries(dashboard?.preguntasPorDia),
    [dashboard?.preguntasPorDia],
  );

  const chatbotData = useMemo(
    () => mapPieItems(dashboard?.distribucionChatbot),
    [dashboard?.distribucionChatbot],
  );

  const userData = useMemo(
    () => mapUserItems(dashboard?.distribucionUsuarios),
    [dashboard?.distribucionUsuarios],
  );

  const categoryData = useMemo(
    () => mapCategoryItems(dashboard?.consultasPorCategoria),
    [dashboard?.consultasPorCategoria],
  );

  return (
    <div className="space-y-6">
      {sinSitios ? (
        <Panel className="p-8 text-center">
          <p className="text-sm font-semibold text-app-texto-secundario">
            No tienes atractivos asignados todavía.
          </p>
        </Panel>
      ) : null}

      {error ? (
        <Panel className="border-app-error bg-red-50 p-4 text-sm font-bold text-app-error">
          {error}
        </Panel>
      ) : null}

      {!sinSitios ? (
        <>
      <DashboardDateFilters
        disabled={isLoading}
        filters={filters}
        onApply={handleApplyFilters}
        onChange={setFilters}
        onClear={handleClearFilters}
      />

      <section className={`grid gap-4 sm:grid-cols-2 ${visibleStats.length >= 6 ? "xl:grid-cols-6" : "xl:grid-cols-5"}`}>
        {visibleStats.map((stat) => {
          const metric = dashboard?.resumen?.[stat.key];

          return (
            <StatCard
              key={stat.key}
              icon={stat.icon}
              label={stat.label}
              loading={isLoading}
              value={formatNumber(metric?.valor || 0)}
            />
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)_minmax(280px,1fr)]">
        <Panel className="p-5">
          <PanelHeader
            title="Preguntas por día"
            eyebrow={alcanceSitio ? "Consultas de tus atractivos" : "Chatbot general y por sitio"}
          />
          <div className="mt-6 h-[300px]">
            {isLoading ? (
              <EmptyState label="Cargando datos..." />
            ) : questionData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={questionData} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="generalFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#00876F" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#00876F" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="siteFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#E98232" stopOpacity={0.16} />
                      <stop offset="100%" stopColor="#E98232" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} />
                  <Tooltip />
                  {alcanceSitio ? null : (
                    <Area type="monotone" dataKey="general" stroke="#00876F" strokeWidth={2.5} fill="url(#generalFill)" />
                  )}
                  <Area type="monotone" dataKey="sitio" stroke="#E98232" strokeWidth={2} fill="url(#siteFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </div>
        </Panel>

        <Panel className="p-5">
          <PanelHeader
            title="Consultas por chatbot"
            eyebrow={alcanceSitio ? "Consultas de chatbot por sitio" : "Chatbot general y por sitio"}
          />
          <div className="mt-6 h-[246px]">
            {isLoading ? (
              <EmptyState label="Cargando datos..." />
            ) : chatbotData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chatbotData}
                    dataKey="value"
                    innerRadius={58}
                    outerRadius={86}
                    paddingAngle={2}
                    stroke="none"
                  >
                    {chatbotData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </div>
          <div className="space-y-3">
            {chatbotData.map((item) => (
              <div key={item.name} className="flex items-center justify-between gap-3 text-sm">
                <span className="flex items-center gap-2 font-medium text-app-texto-secundario">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                  {item.name}
                </span>
                <span className="font-black text-app-texto-primario">
                  {formatNumber(item.value)}
                </span>
              </div>
            ))}
          </div>
        </Panel>

        {alcanceSitio ? null : (
          <Panel className="p-5">
            <PanelHeader
              title="Tipos de usuarios"
              eyebrow="App móvil, dueños y administradores"
            />
            <div className="mt-6 h-[246px]">
              {isLoading ? (
                <EmptyState label="Cargando datos..." />
              ) : userData.length ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={userData}
                      dataKey="value"
                      innerRadius={58}
                      outerRadius={86}
                      paddingAngle={2}
                      stroke="none"
                    >
                      {userData.map((entry) => (
                        <Cell key={entry.key} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState />
              )}
            </div>
            <div className="space-y-3">
              {userData.map((item) => (
                <div key={item.key} className="flex items-center justify-between gap-3 text-sm">
                  <span className="flex items-center gap-2 font-medium text-app-texto-secundario">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: item.color }} />
                    {item.name}
                  </span>
                  <span className="font-black text-app-texto-primario">
                    {formatNumber(item.value)}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        )}
      </section>

      <section className={`grid gap-4 ${alcanceSitio ? "xl:grid-cols-2" : "xl:grid-cols-3"}`}>
        {alcanceSitio ? null : (
        <Panel className="p-5">
          <PanelHeader title="Consultas por categoría" eyebrow="Categorías más consultadas" />
          <div className="mt-6 h-[244px]">
            {isLoading ? (
              <EmptyState label="Cargando datos..." />
            ) : categoryData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={categoryData} layout="vertical" margin={{ left: 56, right: 12, top: 0, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} width={78} />
                  <Bar dataKey="value" fill="#00876F" radius={[0, 4, 4, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </div>
        </Panel>
        )}

        <Panel className="p-5">
          <PanelHeader
            title="Sitios más consultados"
            eyebrow={alcanceSitio ? "Consultas de tus atractivos" : "5 sitios con más consultas"}
          />
          {isLoading ? (
            <div className="mt-6">
              <EmptyState label="Cargando datos..." />
            </div>
          ) : (
            <RankingList items={dashboard?.sitiosMasConsultados?.items || []} />
          )}
        </Panel>

        <Panel className="p-5">
          <PanelHeader
            title="Sitios más guardados"
            eyebrow={alcanceSitio ? "Favoritos de tus atractivos" : "5 sitios con más favoritos"}
          />
          {isLoading ? (
            <div className="mt-6">
              <EmptyState label="Cargando datos..." />
            </div>
          ) : (
            <RankingList accent="#E98232" items={dashboard?.sitiosMasGuardados?.items || []} />
          )}
        </Panel>
      </section>
        </>
      ) : null}
    </div>
  );
}

export default function DashboardPage() {
  const sesion = obtenerSesion();

  if (esDuenoSitio(sesion)) {
    return <OwnerDashboardPage />;
  }

  return <AdminDashboardContent sesion={sesion} />;
}
