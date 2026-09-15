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

export async function obtenerDashboardInicial(filters = {}) {
  const dateParams = buildDateParams(filters);
  const [
    resumen,
    preguntasPorDia,
    distribucionChatbot,
    distribucionUsuarios,
    consultasPorCategoria,
    sitiosMasConsultados,
    sitiosMasGuardados,
  ] = await Promise.all([
    apiClient.get("/admin/dashboard/resumen", {
      params: dateParams,
    }),
    apiClient.get("/admin/dashboard/series", {
      params: {
        metric: "preguntas",
        ...dateParams,
        agrupar_por: "day",
        comparar_por: "tipo_chatbot",
      },
    }),
    apiClient.get("/admin/dashboard/distribucion", {
      params: {
        metric: "preguntas",
        dimension: "tipo_chatbot",
        ...dateParams,
      },
    }),
    apiClient.get("/admin/dashboard/distribucion", {
      params: {
        metric: "usuarios",
        dimension: "estado",
        periodo: "all",
        limit: 4,
      },
    }),
    apiClient.get("/admin/dashboard/distribucion", {
      params: {
        metric: "preguntas",
        dimension: "categoria",
        ...dateParams,
        limit: 6,
      },
    }),
    apiClient.get("/admin/dashboard/ranking", {
      params: {
        tipo: "sitios_consultados",
        ...dateParams,
        limit: 5,
      },
    }),
    apiClient.get("/admin/dashboard/ranking", {
      params: {
        tipo: "sitios_favoritos",
        ...dateParams,
        limit: 5,
      },
    }),
  ]);

  return {
    resumen: resumen.data,
    preguntasPorDia: preguntasPorDia.data,
    distribucionChatbot: distribucionChatbot.data,
    distribucionUsuarios: distribucionUsuarios.data,
    consultasPorCategoria: consultasPorCategoria.data,
    sitiosMasConsultados: sitiosMasConsultados.data,
    sitiosMasGuardados: sitiosMasGuardados.data,
  };
}
