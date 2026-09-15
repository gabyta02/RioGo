import { LogoutIcon } from "./icons";
import { ProfileAvatarWithMeta } from "./ProfileAvatar";

export default function ProfileSidebarCard({
  cargo,
  collapsed = false,
  initials,
  name,
  onLogout,
  onOpenProfile,
  photoUrl,
}) {
  return (
    <div
      className={`flex items-center rounded-2xl border border-white/70 bg-white/86 shadow-[0_10px_30px_rgb(64_48_24/10%)] backdrop-blur-sm ${
        collapsed ? "justify-center p-3" : "gap-2 p-2"
      }`}
    >
      <button
        className={`flex min-w-0 flex-1 items-center rounded-xl transition hover:bg-app-primario-claro/60 focus:outline-none focus:ring-2 focus:ring-app-menu-sage/40 ${
          collapsed ? "justify-center p-1" : "gap-1 p-2"
        }`}
        type="button"
        onClick={onOpenProfile}
        aria-label="Abrir configuración de perfil"
        title="Mi perfil"
      >
        <ProfileAvatarWithMeta
          cargo={cargo}
          collapsed={collapsed}
          initials={initials}
          name={name}
          photoUrl={photoUrl}
        />
      </button>
      {!collapsed ? (
        <button
          className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-app-menu-primario transition hover:bg-app-primario-claro focus:outline-none focus:ring-2 focus:ring-app-menu-sage/40"
          type="button"
          onClick={onLogout}
          aria-label="Cerrar sesión"
          title="Cerrar sesión"
        >
          <LogoutIcon />
        </button>
      ) : null}
    </div>
  );
}
