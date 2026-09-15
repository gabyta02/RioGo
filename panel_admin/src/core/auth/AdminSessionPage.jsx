import { useEffect, useMemo, useState } from "react";
import AdminLayout from "../layouts/AdminLayout";
import QueriesAnalysisPage from "../../modules/analytics/QueriesAnalysisPage";
import CategoriesPage from "../../modules/categories/CategoriesPage";
import ChatbotContentPage from "../../modules/chatbot_content/ChatbotContentPage";
import DashboardPage from "../../modules/dashboard/DashboardPage";
import NoticiasPage from "../../modules/noticias/NoticiasPage";
import RoutesPage from "../../modules/routes/RoutesPage";
import AttractionsPage from "../../modules/attractions/AttractionsPage";
import ActionLogPage from "../../modules/action_log/ActionLogPage";
import AdminAccountsPage from "../../modules/admin_accounts/AdminAccountsPage";
import { puedeAccederVista, primeraVistaPermitida } from "./authStorage";
import SessionManager from "./SessionManager";

const views = {
  dashboard: {
    title: "Dashboard",
    component: <DashboardPage />,
  },
  analytics: {
    title: "Análisis de consultas",
    component: <QueriesAnalysisPage />,
  },
  attractions: {
    title: "Atractivos turísticos",
    component: <AttractionsPage />,
  },
  categories: {
    title: "Categorías y subcategorías",
    component: <CategoriesPage />,
  },
  routes: {
    title: "Rutas turísticas",
    component: <RoutesPage />,
  },
  chatbot_content: {
    title: "Contenido para chatbots",
    component: <ChatbotContentPage />,
  },
  noticias: {
    title: "Noticias turísticas",
    component: <NoticiasPage />,
  },
  action_log: {
    title: "Registro de acciones",
    component: <ActionLogPage />,
  },
  admin_accounts: {
    title: "Cuentas administrativas",
    component: <AdminAccountsPage />,
  },
};

export default function AdminSessionPage({
  session,
  sessionSyncWarning = "",
  onDismissSyncWarning,
  onLogout,
}) {
  const vistaInicial = primeraVistaPermitida(session);
  const [activeView, setActiveView] = useState(() => vistaInicial || "dashboard");

  useEffect(() => {
    if (!vistaInicial) {
      return;
    }
    if (!puedeAccederVista(session, activeView)) {
      setActiveView(vistaInicial);
    }
  }, [activeView, session, vistaInicial]);

  const currentView = useMemo(() => {
    if (!vistaInicial) {
      return null;
    }
    if (puedeAccederVista(session, activeView)) {
      return views[activeView] || views.dashboard;
    }
    return views[vistaInicial] || views.dashboard;
  }, [activeView, session, vistaInicial]);

  if (!vistaInicial || !currentView) {
    return (
      <div className="grid min-h-screen place-items-center bg-app-fondo p-6">
        <div className="max-w-md rounded-2xl border border-app-borde bg-app-tarjeta p-8 text-center shadow-sm">
          <h1 className="text-xl font-black text-app-texto-primario">Acceso denegado</h1>
          <p className="mt-3 text-sm font-semibold text-app-texto-secundario">
            Tu cuenta no tiene módulos asignados en el panel administrativo.
          </p>
          <button
            className="mt-6 rounded-lg bg-app-primario px-4 py-2 text-sm font-black text-white"
            type="button"
            onClick={onLogout}
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <SessionManager />
      {sessionSyncWarning ? (
        <div className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
            <p className="font-semibold">{sessionSyncWarning}</p>
            {onDismissSyncWarning ? (
              <button
                className="shrink-0 rounded-md px-2 py-1 text-xs font-black uppercase tracking-wide text-amber-900 hover:bg-amber-100"
                type="button"
                onClick={onDismissSyncWarning}
              >
                Cerrar
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
      <AdminLayout
        activeView={activeView}
        session={session}
        onLogout={onLogout}
        onViewChange={setActiveView}
        title={currentView.title}
      >
        {currentView.component}
      </AdminLayout>
    </>
  );
}
