import { Fragment, useEffect, useMemo, useState } from "react";
import Panel from "../../core/ui/Panel";
import PanelHeader from "../../core/ui/PanelHeader";
import StatCard from "../../core/ui/StatCard";
import Pagination from "../../core/ui/Pagination";
import ExpandToggleButton from "../../core/ui/ExpandToggleButton";
import ProgressStatusSequence from "../../core/ui/ProgressStatusSequence";
import { DashboardDateFilters } from "../../core/ui/AdminControls";
import { ContentIcon, MapPinIcon, CategoryIcon } from "../../core/ui/icons";
import { obtenerAnalisisSemantico } from "./queriesAnalysisService";
import { getApiErrorMessage } from "../../core/api/errors";

const PAGE_SIZE = 10;
const MIN_GROUP_TOTAL = 20;
const LOADING_STEPS = [
  { id: "filters", label: "Preparando filtros" },
  { id: "history", label: "Consultando historial" },
  { id: "grouping", label: "Agrupando preguntas similares" },
  { id: "variants", label: "Calculando variantes relacionadas" },
  { id: "results", label: "Preparando resultados para mostrar" },
];

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

function SelectFilter({ label, value, options, onChange }) {
  return (
    <label className="block">
      <span className="sr-only">{label}</span>
      <select
        className="h-10 min-w-[190px] rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-semibold text-app-texto-secundario outline-none transition focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <option value="">{label}</option>
        {options.map((option) => {
          const value = typeof option === "string" ? option : option.value;
          const text = typeof option === "string" ? option : option.label;
          return (
          <option key={value} value={value}>
            {text}
          </option>
          );
        })}
      </select>
    </label>
  );
}

function formatCanal(value) {
  if (value === "exploracion") {
    return "Exploración";
  }
  if (value === "pregunta_directa") {
    return "Pregunta directa";
  }
  return "Mixto";
}

export default function QueriesAnalysisPage() {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({
    periodo: "month",
    fecha_inicio: "",
    fecha_fin: "",
    categoria: "",
    subcategoria: "",
    canal: "",
  });
  const [appliedFilters, setAppliedFilters] = useState(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [expandedGroupId, setExpandedGroupId] = useState(null);

  useEffect(() => {
    if (!appliedFilters) {
      return undefined;
    }

    let isActive = true;

    async function loadData() {
      setIsLoading(true);
      setError("");

      try {
        const response = await obtenerAnalisisSemantico(appliedFilters);
        if (isActive) {
          setData(response);
        }
      } catch (err) {
        if (isActive) {
          setError(getApiErrorMessage(err, "No se pudo cargar el análisis"));
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isActive = false;
    };
  }, [appliedFilters]);

  useEffect(() => {
    setPage(1);
    setExpandedGroupId(null);
  }, [appliedFilters]);

  useEffect(() => {
    setExpandedGroupId(null);
  }, [page]);

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

    setError("");
    setAppliedFilters({ ...filters });
  }

  function handleClearFilters() {
    const defaultFilters = {
      periodo: "month",
      fecha_inicio: "",
      fecha_fin: "",
      categoria: "",
      subcategoria: "",
      canal: "",
    };
    setFilters(defaultFilters);
    setAppliedFilters(null);
    setData(null);
    setError("");
    setPage(1);
    setExpandedGroupId(null);
  }

  const categoryOptions = useMemo(() => {
    const values = new Set();
    data?.grupos?.forEach((group) => {
      if (group.categoria) {
        values.add(group.categoria);
      }
    });
    return Array.from(values).sort();
  }, [data]);

  const subcategoryOptions = useMemo(() => {
    const values = new Set();
    data?.grupos?.forEach((group) => {
      if (group.subcategoria) {
        values.add(group.subcategoria);
      }
    });
    return Array.from(values).sort();
  }, [data]);

  const topStats = [
    {
      label: "Preguntas analizadas",
      value: formatNumber(data?.resumen?.preguntas_analizadas || 0),
      icon: <ContentIcon />,
    },
    {
      label: "Mensajes del historial",
      value: formatNumber(data?.resumen?.total_mensajes_historial || 0),
      icon: <CategoryIcon />,
    },
    {
      label: "Preguntas sin embedding",
      value: formatNumber(data?.resumen?.preguntas_sin_embedding || 0),
      icon: <MapPinIcon />,
    },
  ];

  const grupos = data?.grupos || [];
  const hasAppliedSearch = appliedFilters !== null;
  const showSecondaryFilters = Boolean(data);
  const paginatedGroups = useMemo(
    () => grupos.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [grupos, page],
  );

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

      {!hasAppliedSearch ? (
        <Panel className="p-8 text-center">
          <p className="text-sm font-semibold text-app-texto-secundario">
            Selecciona un período y aplica el filtro para analizar consultas.
          </p>
        </Panel>
      ) : null}

      {hasAppliedSearch ? (
        <>
      <section className="grid gap-4 lg:grid-cols-3">
        {topStats.map((stat) => (
          <StatCard key={stat.label} {...stat} loading={isLoading} />
        ))}
      </section>

      <Panel>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-app-borde p-4">
          <PanelHeader
            title="Consultas similares"
          />
          {showSecondaryFilters ? (
          <div className="flex flex-wrap gap-2">
            <SelectFilter
              label="Canal"
              value={filters.canal}
              options={[
                { value: "exploracion", label: "Exploración" },
                { value: "pregunta_directa", label: "Pregunta directa" },
              ]}
              onChange={(canal) => setFilters((current) => ({ ...current, canal }))}
            />
            <SelectFilter
              label="Categoría"
              value={filters.categoria}
              options={categoryOptions}
              onChange={(categoria) => setFilters((current) => ({ ...current, categoria }))}
            />
            <SelectFilter
              label="Subcategoría"
              value={filters.subcategoria}
              options={subcategoryOptions}
              onChange={(subcategoria) => setFilters((current) => ({ ...current, subcategoria }))}
            />
          </div>
          ) : null}
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-app-fondo text-xs font-black uppercase text-app-texto-secundario">
              <tr>
                <th className="px-4 py-3">Pregunta principal</th>
                <th className="px-4 py-3">Consultas</th>
                <th className="px-4 py-3">Variantes</th>
                <th className="px-4 py-3">Categoría / Sitio</th>
                <th className="px-4 py-3">Canal</th>
                <th className="px-4 py-3">Última fecha</th>
                <th className="w-16 px-4 py-3 text-right">Detalle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-borde">
              {isLoading ? (
                <tr>
                  <td className="px-4 py-8" colSpan={7}>
                    <ProgressStatusSequence
                      active
                      className="mx-auto max-w-md"
                      steps={LOADING_STEPS}
                    />
                  </td>
                </tr>
              ) : grupos.length ? (
                paginatedGroups.map((group) => {
                  const relatedQuestions = group.preguntas_relacionadas || [];
                  const isExpanded = expandedGroupId === group.id_grupo;

                  return (
                    <Fragment key={group.id_grupo}>
                      <tr className="align-top">
                        <td className="max-w-[520px] px-4 py-4">
                          <p className="font-black text-app-texto-primario">
                            {group.consulta_representativa}
                          </p>
                          <p className="mt-2 text-xs font-semibold text-app-texto-secundario">
                            Parecido: {Math.round(group.similitud_promedio * 100)}%
                          </p>
                        </td>
                        <td className="px-4 py-4 font-black text-app-texto-primario">
                          {formatNumber(group.total_consultas)}
                        </td>
                        <td className="px-4 py-4 font-black text-app-texto-primario">
                          {formatNumber(relatedQuestions.length)}
                        </td>
                        <td className="px-4 py-4">
                          <p className="font-bold text-app-texto-primario">
                            {group.categoria || group.entidad || "Sin clasificar"}
                          </p>
                          <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
                            {group.subcategoria || group.entidad || "Sin subcategoría"}
                          </p>
                        </td>
                        <td className="px-4 py-4 font-semibold text-app-texto-secundario">
                          {formatCanal(group.canal)}
                        </td>
                        <td className="px-4 py-4 font-semibold text-app-texto-secundario">
                          {formatDate(group.ultima_fecha)}
                        </td>
                        <td className="px-4 py-4 text-right">
                          <ExpandToggleButton
                            className="ml-auto"
                            expanded={isExpanded}
                            size="sm"
                            onClick={() => {
                              setExpandedGroupId((current) => (
                                current === group.id_grupo ? null : group.id_grupo
                              ));
                            }}
                          />
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr className="bg-app-fondo/70">
                          <td className="px-4 py-4" colSpan={7}>
                            <div className="space-y-2">
                              {relatedQuestions.map((question) => (
                                <div
                                  className="grid gap-3 rounded-lg border border-app-borde bg-app-tarjeta px-4 py-3 md:grid-cols-[1fr_auto_auto]"
                                  key={`${group.id_grupo}-${question.pregunta}`}
                                >
                                  <div>
                                    <p className="font-bold text-app-texto-primario">
                                      {question.pregunta}
                                    </p>
                                    <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
                                      {question.categoria || question.entidad || "Sin clasificar"}
                                      {" · "}
                                      {question.subcategoria || question.entidad || "Sin subcategoría"}
                                    </p>
                                  </div>
                                  <div className="font-black text-app-texto-primario">
                                    {formatNumber(question.total_consultas)} consultas
                                  </div>
                                  <div className="font-semibold text-app-texto-secundario">
                                    {formatDate(question.ultima_fecha)}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })
              ) : (
                <tr>
                  <td className="px-4 py-8 text-center font-semibold text-app-texto-secundario" colSpan={7}>
                    No hay grupos con al menos {MIN_GROUP_TOTAL} consultas relacionadas.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {grupos.length > PAGE_SIZE ? (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={grupos.length}
            onPageChange={setPage}
          />
        ) : null}
      </Panel>
        </>
      ) : null}
    </div>
  );
}
