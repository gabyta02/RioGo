import { text } from "../typography";

const sizeClasses = {
  sm: "h-8 w-8 text-[10px]",
  md: "h-10 w-10 text-xs",
  lg: "h-14 w-14 text-lg",
  xl: "h-20 w-20 text-xl",
};

export function getProfileInitials(name = "") {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "AD";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

export function resolveProfilePhotoUrl(fotoUrl) {
  if (!fotoUrl) return null;
  if (fotoUrl.startsWith("http://") || fotoUrl.startsWith("https://")) {
    return fotoUrl;
  }
  return fotoUrl.startsWith("/") ? fotoUrl : `/${fotoUrl}`;
}

export default function ProfileAvatar({
  className = "",
  initials,
  name,
  showOnline = false,
  size = "md",
  src,
}) {
  const sizeClass = sizeClasses[size] || sizeClasses.md;

  return (
    <div className={`relative inline-flex shrink-0 ${className}`}>
      {src ? (
        <img
          alt={name ? `Foto de ${name}` : "Foto de perfil"}
          className={`rounded-full object-cover ${sizeClass}`}
          src={src}
        />
      ) : (
        <span
          className={`grid place-items-center rounded-full bg-[#dcecd9] font-black text-app-menu-primario ${sizeClass}`}
          aria-hidden="true"
        >
          {initials}
        </span>
      )}
      {showOnline ? (
        <span className="absolute bottom-0.5 right-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-[#22a447]" />
      ) : null}
      {name ? <span className="sr-only">{name}</span> : null}
    </div>
  );
}

export function ProfileAvatarWithMeta({ cargo, collapsed = false, initials, name, photoUrl }) {
  if (collapsed) {
    return <ProfileAvatar initials={initials} name={name} showOnline size="lg" src={photoUrl} />;
  }

  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <ProfileAvatar initials={initials} name={name} showOnline size="lg" src={photoUrl} />
      <div className="min-w-0 flex-1 text-left">
        <p className={`truncate ${text.entityTitle} text-app-menu-primario`}>{name}</p>
        {cargo ? <p className={`mt-1 truncate ${text.entityMeta} text-[#18558d]`}>{cargo}</p> : null}
      </div>
    </div>
  );
}
