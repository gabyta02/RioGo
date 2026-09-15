import apiClient from "../../core/api/client";

function buildDateParams(filters = {}) {
  const periodo = filters.periodo || "month";
  const params = { periodo };

  if (periodo === "custom") {
    params.fecha_inicio = filters.fecha_inicio || undefined;
    params.fecha_fin = filters.fecha_fin || undefined;
  }

  return params;
}

export async function obtenerAnalisisSemantico({
  categoria,
  subcategoria,
  canal,
  ...dateFilters
} = {}) {
  const { data } = await apiClient.get("/admin/dashboard/semantica", {
    params: {
      ...buildDateParams(dateFilters),
      limit: 30,
      max_consultas_analisis: 10000,
      min_total_consultas: 20,
      ...(categoria ? { categoria } : {}),
      ...(subcategoria ? { subcategoria } : {}),
      ...(canal ? { canal } : {}),
    },
  });

  return data;
}
