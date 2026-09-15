import { useEffect, useState } from "react";
import {
  CategoryIcon,
  ChartIcon,
  ContentIcon,
  DashboardIcon,
  MapPinIcon,
  NewsIcon,
  RouteIcon,
  UserIcon,
} from "../ui/icons";
import ProfileSidebarCard from "../ui/ProfileSidebarCard";
import ProfileAvatar, { getProfileInitials, resolveProfilePhotoUrl } from "../ui/ProfileAvatar";
import ProfileSettingsModal from "../../modules/profile/ProfileSettingsModal";
import { limpiarSesion, puedeAccederVista } from "../auth/authStorage";
import { cerrarSesion as cerrarSesionApi } from "../auth/authService";

const logoSrc = `${import.meta.env.BASE_URL}assets/logo.png`;
const topDecorSrc = `${import.meta.env.BASE_URL}assets/imagen_arriba.png`;
const bottomDecorSrc = `${import.meta.env.BASE_URL}assets/imagen_de_abajo.png`;
const SIDEBAR_COLLAPSED_KEY = "riobambatour_admin_sidebar_collapsed";

const menuSections = [
  {
    title: "General",
    items: [
      { id: "dashboard", label: "Dashboard", icon: <DashboardIcon /> },
      { id: "analytics", label: "Análisis de consultas", icon: <ChartIcon /> },
    ],
  },
  {
    title: "Contenido",
    items: [
      { id: "attractions", label: "Atractivos turísticos", icon: <MapPinIcon /> },
      { id: "categories", label: "Categorías y subcategorías", icon: <CategoryIcon /> },
      { id: "routes", label: "Rutas turísticas", icon: <RouteIcon /> },
      { id: "chatbot_content", label: "Contenido para chatbots", icon: <ContentIcon /> },
      { id: "noticias", label: "Noticias turísticas", icon: <NewsIcon /> },
    ],
  },
  {
    title: "Sistema",
    items: [
      { id: "admin_accounts", label: "Cuentas administrativas", icon: <UserIcon /> },
      { id: "action_log", label: "Registro de acciones", icon: <ContentIcon /> },
    ],
  },
];

function CollapseIcon({ collapsed = false }) {
  return (
    <svg
      aria-hidden="true"
      className="h-5 w-5 shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="2.5"
    >
      {collapsed ? (
        <path strokeLinecap="round" strokeLinejoin="round" d="m9 6 6 6-6 6M5 6l6 6-6 6" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" d="m15 6-6 6 6 6M19 6l-6 6 6 6" />
      )}
    </svg>
  );
}

function SidebarItem({ active = false, collapsed = false, disabled = false, icon, label, onClick }) {
  return (
    <button
      className={`group relative flex h-12 w-full items-center rounded-2xl text-left text-sm transition ${
        collapsed ? "justify-center px-0" : "gap-3 px-3"
      } ${
        disabled
          ? "cursor-not-allowed text-app-menu-inactivo/50"
          : active
            ? "bg-[#dfeede] font-black text-app-menu-primario shadow-inner ring-1 ring-[#bed4c7]"
            : "font-semibold text-[#0f4e84] hover:bg-white/65 hover:text-app-menu-primario"
      }`}
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={collapsed ? label : undefined}
    >
      <span
        className={`grid h-9 w-9 shrink-0 place-items-center rounded-full transition ${
          active
            ? "bg-app-menu-primario text-white shadow-[0_7px_18px_rgb(0_77_64/28%)]"
            : "text-[#0f4e84] group-hover:bg-app-primario-claro"
        }`}
      >
        {icon}
      </span>
      {!collapsed ? <span className="min-w-0 flex-1 leading-tight">{label}</span> : null}
    </button>
  );
}

function filtrarMenu(session) {
  return menuSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (item.disabled || !item.id) {
          return !item.disabled;
        }
        return puedeAccederVista(session, item.id);
      }),
    }))
    .filter((section) => section.items.length > 0);
}

export default function AdminLayout({ activeView, children, onLogout, onViewChange, session, title }) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [profileOpen, setProfileOpen] = useState(false);
  const [sessionState, setSessionState] = useState(session);
  const sections = filtrarMenu(sessionState);
  const displayName =
    sessionState?.usuario?.nombre_completo || sessionState?.nombre_completo || sessionState?.usuario?.username || "Admin";
  const cargoLabel =
    sessionState?.usuario?.cargo_nombre || sessionState?.cargo_nombre || (sessionState?.rol === "super-admin" ? "Super administrador" : "Administrador");
  const iniciales = getProfileInitials(displayName);
  const photoUrl = resolveProfilePhotoUrl(sessionState?.foto_url || sessionState?.usuario?.foto_url);

  useEffect(() => {
    setSessionState(session);
  }, [session]);

  async function handleLogout() {
    try {
      await cerrarSesionApi();
    } catch {
      // Si el token ya expiro o falla la red, igual se limpia la sesion local.
    }
    limpiarSesion();
    onLogout();
  }

  function toggleCollapsed() {
    setCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, next ? "1" : "0");
      } catch {
        // Persistir la preferencia es útil, pero no indispensable.
      }
      return next;
    });
  }

  return (
    <main
      className={`min-h-screen bg-[#f8f5ef] text-app-texto-primario transition-[padding] duration-300 lg:grid ${
        collapsed ? "lg:grid-cols-[116px_minmax(0,1fr)]" : "lg:grid-cols-[332px_minmax(0,1fr)]"
      }`}
    >
      <aside
        className={`relative m-0 flex min-h-screen flex-col overflow-visible border-r border-[#ded8ca] bg-[#fbf6ea] text-app-menu-primario shadow-[18px_0_45px_rgb(53_38_18/10%)] transition-[width] duration-300 ${
          collapsed ? "lg:w-[116px]" : "lg:w-[332px]"
        }`}
      >
        <div className="pointer-events-none absolute inset-0 overflow-hidden">
          <img
            alt=""
            className={`absolute left-0 top-0 w-full object-cover transition-all duration-300 ${
              collapsed ? "h-[250px] object-[47%_top]" : "h-[252px] object-top"
            }`}
            src={topDecorSrc}
          />
          <img
            alt=""
            className={`absolute bottom-0 left-0 w-full object-cover transition-all duration-300 ${
              collapsed ? "h-[152px] object-[50%_bottom]" : "h-[180px] object-bottom"
            }`}
            src={bottomDecorSrc}
          />
          <div className="absolute inset-0 bg-gradient-to-b from-[#fbf6ea]/20 via-[#fbf6ea]/88 to-[#fbf6ea]/20" />
          <div className="absolute inset-x-0 top-[200px] h-32 bg-gradient-to-b from-transparent to-[#fbf6ea]" />
          <div className="absolute inset-x-0 bottom-[126px] h-28 bg-gradient-to-t from-transparent to-[#fbf6ea]" />
        </div>

        <button
          className="absolute -right-5 top-[47%] z-30 grid h-16 w-10 place-items-center rounded-full border border-[#e2dac8] bg-[#fbf7ed] text-app-menu-primario shadow-[0_10px_25px_rgb(53_38_18/14%)] transition hover:bg-white focus:outline-none focus:ring-4 focus:ring-app-primario-claro"
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Expandir menú lateral" : "Contraer menú lateral"}
          title={collapsed ? "Expandir menú lateral" : "Contraer menú lateral"}
        >
          <CollapseIcon collapsed={collapsed} />
        </button>

        <div className={`relative z-10 flex gap-3 pb-2 pt-7 ${collapsed ? "flex-col items-center px-3 text-center" : "items-start px-7"}`}>
          <img
            className={`${collapsed ? "h-14 w-14" : "h-14 w-14"} rounded-full border border-white/80 bg-white object-cover shadow-sm`}
            src={logoSrc}
            alt="RioGo"
          />
          {!collapsed ? (
            <div className="min-w-0 pt-1">
              <p className="text-3xl font-black leading-none tracking-normal text-app-menu-primario">RioGo</p>
              <p className="mt-2 text-sm font-semibold text-[#18558d]">Panel administrativo</p>
            </div>
          ) : (
            <div className="min-w-0">
              <p className="text-xl font-black leading-none tracking-normal text-app-menu-primario">RioGo</p>
              <p className="mt-1 text-[11px] font-semibold leading-tight text-[#18558d]">Panel administrativo</p>
            </div>
          )}
        </div>

        <div className={`relative z-10 ${collapsed ? "px-3 pb-4 pt-[116px]" : "px-6 pb-5 pt-[120px]"}`}>
          <ProfileSidebarCard
            cargo={cargoLabel}
            collapsed={collapsed}
            initials={iniciales}
            name={displayName}
            photoUrl={photoUrl}
            onLogout={handleLogout}
            onOpenProfile={() => setProfileOpen(true)}
          />
        </div>

        <nav className={`relative z-10 min-h-0 flex-1 overflow-y-auto pb-6 ${collapsed ? "px-4" : "px-6"}`}>
          {sections.map((section, sectionIndex) => (
            <section key={section.title} className={sectionIndex ? "mt-6" : ""}>
              {!collapsed ? (
                <div className="mb-3 flex items-center gap-3">
                  <h2 className="shrink-0 text-[11px] font-black uppercase tracking-[0.24em] text-[#18558d]">
                    {section.title}
                  </h2>
                  <span className="h-px flex-1 bg-[#d7d1c4]" />
                </div>
              ) : sectionIndex ? (
                <div className="mx-auto mb-4 h-px w-10 bg-[#d7d1c4]" />
              ) : null}
              <div className="space-y-1.5">
                {section.items.map((item) => (
                  <SidebarItem
                    key={item.label}
                    {...item}
                    collapsed={collapsed}
                    active={item.id === activeView}
                    onClick={() => item.id && onViewChange(item.id)}
                  />
                ))}
              </div>
            </section>
          ))}
        </nav>
      </aside>

      <section className="min-w-0 overflow-x-hidden">
        <header className="flex h-16 items-center justify-between gap-3 border-b border-app-borde bg-app-tarjeta px-4 sm:px-6">
          <h1 className="min-w-0 truncate text-xl font-black text-app-texto-primario">{title}</h1>
          <button
            className="rounded-full transition hover:opacity-90 focus:outline-none focus:ring-4 focus:ring-app-primario-claro"
            type="button"
            onClick={() => setProfileOpen(true)}
            aria-label="Abrir perfil"
          >
            <ProfileAvatar initials={iniciales} name={displayName} size="md" src={photoUrl} />
          </button>
        </header>
        <div className="min-w-0 p-4 sm:p-6">{children}</div>
      </section>

      {profileOpen ? (
        <ProfileSettingsModal
          onClose={() => setProfileOpen(false)}
          onLogout={onLogout}
          onSessionUpdated={setSessionState}
        />
      ) : null}
    </main>
  );
}
