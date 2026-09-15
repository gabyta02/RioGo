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

export async function obtenerDashboardDueno(filters = {}) {
  const dateParams = buildDateParams(filters);
  const [resumen, preguntasPorDia, sitiosFavoritos, temasFrecuentes, ultimasPreguntas] =
    await Promise.all([
      apiClient.get("/admin/dashboard/resumen", {
        params: dateParams,
      }),
      apiClient.get("/admin/dashboard/series", {
        params: {
          metric: "preguntas",
          ...dateParams,
          agrupar_por: "day",
          comparar_por: "tipo_chatbot",
          tipo_chatbot: "sitio",
        },
      }),
      apiClient.get("/admin/dashboard/ranking", {
        params: {
          tipo: "sitios_favoritos",
          ...dateParams,
          limit: 5,
        },
      }),
      apiClient.get("/admin/dashboard/semantica", {
        params: {
          ...dateParams,
          canal: "pregunta_directa",
          limit: 8,
          max_consultas_analisis: 10000,
          min_total_consultas: 1,
        },
      }),
      apiClient.get("/admin/dashboard/consultas", {
        params: {
          ...dateParams,
          tipo_chatbot: "sitio",
          page: 1,
          page_size: 6,
          orden: "fecha_desc",
        },
      }),
    ]);

  return {
    resumen: resumen.data,
    preguntasPorDia: preguntasPorDia.data,
    sitiosFavoritos: sitiosFavoritos.data,
    temasFrecuentes: temasFrecuentes.data,
    ultimasPreguntas: ultimasPreguntas.data,
  };
}
