import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import Panel from "../../core/ui/Panel";
import PanelHeader from "../../core/ui/PanelHeader";
import StatCard from "../../core/ui/StatCard";
import { DashboardDateFilters } from "../../core/ui/AdminControls";
import { ChartIcon, ContentIcon, MapPinIcon } from "../../core/ui/icons";
import { getApiErrorMessage } from "../../core/api/errors";
import { obtenerDashboardDueno } from "./ownerDashboardService";

function formatNumber(value = 0) {
  return new Intl.NumberFormat("es-EC").format(value);
}

function formatDate(value) {
  if (!value) {
    return "";
  }
  return new Intl.DateTimeFormat("es-EC", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
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
      const current = byLabel.get(point.label) || { day: point.label, sitio: 0 };
      current[serie.key] = point.valor;
      byLabel.set(point.label, current);
    });
  });

  return Array.from(byLabel.values());
}

function mapTopicItems(response) {
  return (response?.grupos || []).map((group) => ({
    name: group.consulta_representativa,
    value: group.total_consultas,
  }));
}

function RankingList({ items }) {
  if (!items.length) {
    return <EmptyState />;
  }

  const max = Math.max(...items.map((item) => item.valor), 1);

  return (
    <ol className="mt-6 space-y-4">
      {items.map((item) => (
        <li key={`${item.posicion}-${item.nombre}`}>
          <div className="flex items-center justify-between gap-4 text-sm">
            <span className="truncate font-bold text-app-texto-primario">{item.nombre}</span>
            <span className="shrink-0 font-black text-app-texto-primario">
              {formatNumber(item.valor)}
            </span>
          </div>
          <div className="mt-2 h-1.5 rounded-full bg-app-primario-claro">
            <div
              className="h-1.5 rounded-full bg-[#E98232]"
              style={{ width: `${(item.valor / max) * 100}%` }}
            />
          </div>
        </li>
      ))}
    </ol>
  );
}

export default function OwnerDashboardPage() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({
    periodo: "month",
    fecha_inicio: "",
    fecha_fin: "",
  });
  const [appliedFilters, setAppliedFilters] = useState(filters);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    async function loadDashboard() {
      setIsLoading(true);
      setError("");

      try {
        const data = await obtenerDashboardDueno(appliedFilters);
        if (isActive) {
          setDashboard(data);
        }
      } catch (err) {
        if (isActive) {
          setError(getApiErrorMessage(err, "No se pudo cargar el dashboard de tu sitio"));
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
  }, [appliedFilters]);

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
  const topicData = useMemo(
    () => mapTopicItems(dashboard?.temasFrecuentes),
    [dashboard?.temasFrecuentes],
  );

  const stats = [
    {
      label: "Preguntas a tu sitio",
      value: formatNumber(dashboard?.resumen?.preguntas_chatbots?.valor || 0),
      icon: <ContentIcon />,
    },
    {
      label: "Usuarios con favorito",
      value: formatNumber(dashboard?.resumen?.favoritos_guardados?.valor || 0),
      icon: <ChartIcon />,
    },
    {
      label: "Atractivos asignados",
      value: formatNumber(dashboard?.resumen?.atractivos_activos?.valor || 0),
      icon: <MapPinIcon />,
    },
  ];

  return (
    <div className="space-y-6">
      <DashboardDateFilters
        disabled={isLoading}
        filters={filters}
        onApply={handleApplyFilters}
        onChange={setFilters}
        onClear={handleClearFilters}
      />

      {error ? (
        <Panel className="border-app-error bg-red-50 p-4 text-sm font-bold text-app-error">
          {error}
        </Panel>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-3">
        {stats.map((stat) => (
          <StatCard key={stat.label} {...stat} loading={isLoading} />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(340px,1fr)]">
        <Panel className="p-5">
          <PanelHeader
            title="Preguntas por día"
            eyebrow="Actividad del chatbot de tus sitios"
          />
          <div className="mt-6 h-[300px]">
            {isLoading ? (
              <EmptyState label="Cargando datos..." />
            ) : questionData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={questionData} margin={{ left: -20, right: 8, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="ownerSiteFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="0%" stopColor="#E98232" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#E98232" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="sitio" stroke="#E98232" strokeWidth={2.5} fill="url(#ownerSiteFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </div>
        </Panel>

        <Panel className="p-5">
          <PanelHeader title="Sitios guardados" eyebrow="Favoritos por atractivo asignado" />
          {isLoading ? (
            <div className="mt-6">
              <EmptyState label="Cargando datos..." />
            </div>
          ) : (
            <RankingList items={dashboard?.sitiosFavoritos?.items || []} />
          )}
        </Panel>
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Panel className="p-5">
          <PanelHeader title="Temas más preguntados" eyebrow="Grupos frecuentes de preguntas" />
          <div className="mt-6 h-[300px]">
            {isLoading ? (
              <EmptyState label="Cargando datos..." />
            ) : topicData.length ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={topicData} layout="vertical" margin={{ left: 12, right: 12, top: 0, bottom: 0 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#64748B" }} width={150} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#00876F" radius={[0, 4, 4, 0]} barSize={16} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyState />
            )}
          </div>
        </Panel>

        <Panel className="p-5">
          <PanelHeader title="Últimas preguntas" eyebrow="Consultas recientes del chatbot del sitio" />
          {isLoading ? (
            <div className="mt-6">
              <EmptyState label="Cargando datos..." />
            </div>
          ) : dashboard?.ultimasPreguntas?.items?.length ? (
            <div className="mt-5 divide-y divide-app-borde">
              {dashboard.ultimasPreguntas.items.map((item) => (
                <article key={`${item.tipo_chatbot}-${item.id_mensaje}`} className="py-4">
                  <p className="font-bold text-app-texto-primario">{item.pregunta}</p>
                  <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
                    {item.sitio || "Tu sitio"} · {formatDate(item.fecha)}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <div className="mt-6">
              <EmptyState />
            </div>
          )}
        </Panel>
      </section>
    </div>
  );
}
