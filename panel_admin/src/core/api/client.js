import axios from "axios";
import {
  guardarSesionTrasRefresh,
  limpiarSesion,
  notificarSesionExpirada,
  obtenerSesion,
  registrarActividadSesion,
} from "../auth/authStorage";

const apiClient = axios.create({
  baseURL: "/api/v1",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

let refreshPromise = null;

function getErrorDetail(error) {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item?.detail || "").join(" ");
  }
  if (detail && typeof detail === "object") {
    return detail.msg || detail.detail || "";
  }
  return String(detail || "");
}

function isSessionExpiredError(error) {
  const detail = getErrorDetail(error).toLowerCase();
  return (
    detail.includes("sesion expirada") ||
    detail.includes("sesión expirada") ||
    detail.includes("inactividad") ||
    detail.includes("token invalido") ||
    detail.includes("token inválido") ||
    detail.includes("token invalido o expirado") ||
    detail.includes("token inválido o expirado") ||
    detail.includes("refresh token invalido") ||
    detail.includes("refresh token inválido")
  );
}

apiClient.interceptors.request.use((config) => {
  const session = obtenerSesion();
  config.headers = config.headers || {};
  const url = config.url || "";

  if (session?.token) {
    config.headers.Authorization = `Bearer ${session.token}`;
  }
  if (session?.admin_sesion_id) {
    config.headers["X-Admin-Session-Id"] = session.admin_sesion_id;
  }

  const isAuthLifecycleRequest =
    url.includes("/auth/login") ||
    url.includes("/auth/refresh") ||
    url.includes("/auth/logout") ||
    url.includes("/auth/admin-session/refresh");
  if (session?.admin_sesion_id && !isAuthLifecycleRequest) {
    registrarActividadSesion();
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const status = error?.response?.status;
    const url = originalRequest?.url || "";
    const hasSession = Boolean(obtenerSesion()?.token);
    const isAuthRequest = url.includes("/auth/login") || url.includes("/auth/refresh");

    if (status === 401 && hasSession && isSessionExpiredError(error)) {
      notificarSesionExpirada();
      return Promise.reject(error);
    }

    if (status !== 401 || !originalRequest || originalRequest._retry || !hasSession || isAuthRequest) {
      if (status === 401 && hasSession && url.includes("/auth/refresh")) {
        notificarSesionExpirada();
      }
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    try {
      if (!refreshPromise) {
        refreshPromise = apiClient.post("/auth/refresh").then((response) => response.data);
      }

      const nextSession = await refreshPromise;
      guardarSesionTrasRefresh(nextSession);
      originalRequest.headers = originalRequest.headers || {};
      originalRequest.headers.Authorization = `Bearer ${nextSession.token}`;
      return apiClient(originalRequest);
    } catch (refreshError) {
      notificarSesionExpirada();
      return Promise.reject(refreshError);
    } finally {
      refreshPromise = null;
    }
  }
);

export function cerrarSesionLocal() {
  limpiarSesion();
  notificarSesionExpirada();
}

export default apiClient;
