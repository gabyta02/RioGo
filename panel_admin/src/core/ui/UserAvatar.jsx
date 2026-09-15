import { text } from "../typography";

export default function UserAvatar({ initials, name, size = "md" }) {
  const sizeClass = size === "sm" ? "h-8 w-8 text-[10px]" : "h-10 w-10 text-xs";

  return (
    <div className="flex min-w-0 items-center gap-3">
      <span
        className={`grid shrink-0 place-items-center rounded-full bg-app-primario-claro font-black text-app-primario ${sizeClass}`}
        aria-hidden="true"
      >
        {initials}
      </span>
      {name ? <p className={`truncate ${text.entityTitle}`}>{name}</p> : null}
    </div>
  );
}
