import { useEffect, useRef } from "react";
import {
  guardarSesionTrasRefresh,
  leerSesionAlmacenada,
  obtenerSesion,
  notificarSesionExpirada,
  registrarActividadSesion,
  registrarRenovacionSesionAdmin,
} from "./authStorage";
import { renovarSesionAdmin, renovarToken } from "./authService";

const REFRESH_CHECK_INTERVAL = 10000;
const ACTIVITY_THROTTLE_MS = 15000;
const ACTIVITY_EVENTS = [
  "click",
  "keydown",
  "mousemove",
  "scroll",
  "touchstart",
];

export default function SessionManager() {
  const timerRef = useRef(null);
  const isRefreshingRef = useRef(false);
  const isRefreshingAdminSessionRef = useRef(false);
  const lastActivityWriteRef = useRef(0);

  useEffect(() => {
    function checkAndRefreshSession() {
      const storedSession = leerSesionAlmacenada();
      if (storedSession?.inactivity_expires_at && Date.now() >= storedSession.inactivity_expires_at) {
        notificarSesionExpirada();
        return;
      }

      const session = obtenerSesion();
      if (!session) {
        return;
      }

      const now = Date.now();

      if (session.inactivity_expires_at && now >= session.inactivity_expires_at) {
        notificarSesionExpirada();
        return;
      }

      if (
        session.next_token_refresh &&
        now >= session.next_token_refresh &&
        !isRefreshingRef.current
      ) {
        isRefreshingRef.current = true;
        renovarToken()
          .then((newSession) => {
            guardarSesionTrasRefresh(newSession);
          })
          .catch(() => {
            notificarSesionExpirada();
          })
          .finally(() => {
            isRefreshingRef.current = false;
          });
      }

      if (
        session.admin_sesion_id &&
        session.admin_session_refresh_at &&
        now >= session.admin_session_refresh_at &&
        session.last_activity_at > session.last_admin_session_refresh_at &&
        !isRefreshingAdminSessionRef.current
      ) {
        isRefreshingAdminSessionRef.current = true;
        renovarSesionAdmin()
          .then(() => {
            registrarRenovacionSesionAdmin();
          })
          .catch(() => {
            notificarSesionExpirada();
          })
          .finally(() => {
            isRefreshingAdminSessionRef.current = false;
          });
      }
    }

    function handleActivity() {
      const storedSession = leerSesionAlmacenada();
      if (storedSession?.inactivity_expires_at && Date.now() >= storedSession.inactivity_expires_at) {
        notificarSesionExpirada();
        return;
      }

      const session = obtenerSesion();
      if (!session) {
        return;
      }

      const now = Date.now();
      if (session.inactivity_expires_at && now >= session.inactivity_expires_at) {
        notificarSesionExpirada();
        return;
      }

      if (document.visibilityState === "hidden") {
        return;
      }

      if (now - lastActivityWriteRef.current < ACTIVITY_THROTTLE_MS) {
        return;
      }

      lastActivityWriteRef.current = now;
      registrarActividadSesion();
    }

    ACTIVITY_EVENTS.forEach((eventName) => {
      window.addEventListener(eventName, handleActivity, { passive: true });
    });
    document.addEventListener("visibilitychange", handleActivity);
    timerRef.current = setInterval(checkAndRefreshSession, REFRESH_CHECK_INTERVAL);
    checkAndRefreshSession();

    return () => {
      ACTIVITY_EVENTS.forEach((eventName) => {
        window.removeEventListener(eventName, handleActivity);
      });
      document.removeEventListener("visibilitychange", handleActivity);
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  return null;
}
