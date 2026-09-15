import { useEffect, useState } from "react";
import AdminSessionPage from "./core/auth/AdminSessionPage";
import AccountRecoveryPage from "./core/auth/AccountRecoveryPage";
import LoginPage from "./core/auth/LoginPage";
import VerificationCodePage from "./core/auth/VerificationCodePage";
import {
  AUTH_SESSION_EXPIRED_EVENT,
  actualizarPermisosSesion,
  enriquecerSesionDesdePerfil,
  guardarSesion,
  limpiarSesion,
  notificarSesionExpirada,
  obtenerSesion,
  leerSesionAlmacenada,
  esSesionPanel,
} from "./core/auth/authStorage";
import { obtenerUsuarioActual } from "./core/auth/authService";

function obtenerSesionAdmin() {
  const rawSession = leerSesionAlmacenada();
  if (rawSession?.inactivity_expires_at && Date.now() >= rawSession.inactivity_expires_at) {
    limpiarSesion();
    return null;
  }

  const storedSession = obtenerSesion();
  if (!storedSession || !esSesionPanel(storedSession)) {
    if (storedSession) {
      limpiarSesion();
    }
    return null;
  }

  return storedSession;
}

function haySesionAdminVencida() {
  const rawSession = leerSesionAlmacenada();
  return Boolean(rawSession?.inactivity_expires_at && Date.now() >= rawSession.inactivity_expires_at);
}

export default function App() {
  const isAccountPage = window.location.pathname.startsWith("/account");
  const sesionVencidaInicial = haySesionAdminVencida();
  const [session, setSession] = useState(() => obtenerSesionAdmin());
  const [verification, setVerification] = useState(null);
  const [sessionSyncWarning, setSessionSyncWarning] = useState("");
  const [loginNotice, setLoginNotice] = useState(() =>
    sesionVencidaInicial
      ? "Tu sesión se cerró por inactividad. Inicia sesión nuevamente."
      : "",
  );

  useEffect(() => {
    function handleSessionExpired(event) {
      setSession(null);
      setVerification(null);
      setSessionSyncWarning("");
      setLoginNotice(
        event?.detail?.motivo ||
        "Tu sesión se cerró por inactividad. Inicia sesión nuevamente.",
      );
    }

    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired);
    return () => {
      window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired);
    };
  }, []);

  useEffect(() => {
    let isActive = true;
    const sesionInicial = obtenerSesionAdmin();
    if (!sesionInicial) {
      return undefined;
    }

    async function sincronizarSesionAlIniciar() {
      if (
        sesionInicial.inactivity_expires_at &&
        Date.now() >= sesionInicial.inactivity_expires_at
      ) {
        notificarSesionExpirada();
        return;
      }

      try {
        const perfil = await obtenerUsuarioActual();
        if (!isActive) {
          return;
        }
        const sesionActualizada = actualizarPermisosSesion(perfil);
        if (sesionActualizada) {
          setSession(sesionActualizada);
        }
        setSessionSyncWarning("");
      } catch (error) {
        if (isActive) {
          if (error?.response?.status === 401) {
            notificarSesionExpirada();
            return;
          }
          setSessionSyncWarning(
            "No se pudo sincronizar permisos. Cierra sesión e ingresa de nuevo.",
          );
        }
      }
    }

    sincronizarSesionAlIniciar();

    return () => {
      isActive = false;
    };
  }, []);

  async function handleLoginSuccess(nextSession) {
    if (!esSesionPanel(nextSession)) {
      return;
    }
    if (!nextSession.admin_sesion_id) {
      limpiarSesion();
      setSession(null);
      setVerification(null);
      setSessionSyncWarning("");
      setLoginNotice(
        "No se pudo iniciar la sesión administrativa. Intenta iniciar sesión nuevamente.",
      );
      return;
    }

    let sessionEnriquecida = nextSession;
    setLoginNotice("");
    setSessionSyncWarning("");
    try {
      guardarSesion(nextSession);
      const perfil = await obtenerUsuarioActual();
      sessionEnriquecida = enriquecerSesionDesdePerfil(nextSession, perfil);
    } catch {
      setSessionSyncWarning(
        "No se pudo sincronizar permisos. Algunas funciones pueden no estar disponibles.",
      );
      sessionEnriquecida = nextSession;
    }

    guardarSesion(sessionEnriquecida);
    setSession(sessionEnriquecida);
    setVerification(null);
  }

  if (isAccountPage) {
    return <AccountRecoveryPage />;
  }

  if (session) {
    return (
      <AdminSessionPage
        session={session}
        sessionSyncWarning={sessionSyncWarning}
        onDismissSyncWarning={() => setSessionSyncWarning("")}
        onLogout={() => {
          setSession(null);
          setSessionSyncWarning("");
          setLoginNotice("");
        }}
      />
    );
  }

  if (verification) {
    return (
      <VerificationCodePage
        {...verification}
        onBack={() => setVerification(null)}
        onLoginSuccess={handleLoginSuccess}
        onTokenRefresh={(tokenVerificacion) => {
          setVerification((current) => ({
            ...current,
            tokenVerificacion,
          }));
        }}
      />
    );
  }

  return (
    <LoginPage
      notice={loginNotice}
      onLoginSuccess={handleLoginSuccess}
      onVerificationRequired={setVerification}
    />
  );
}
