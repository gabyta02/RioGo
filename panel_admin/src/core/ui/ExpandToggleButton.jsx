import { ChevronDownIcon } from "./icons";

const noop = () => {};

const sizeClasses = {
  sm: "h-9 w-9",
  md: "h-11 w-11",
};

export default function ExpandToggleButton({
  className = "",
  expanded = false,
  onClick,
  size = "md",
}) {
  return (
    <button
      className={`grid shrink-0 place-items-center rounded-lg border transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro ${
        sizeClasses[size] || sizeClasses.md
      } ${
        expanded
          ? "border-app-primario bg-app-primario-claro text-app-primario"
          : "border-app-borde bg-app-tarjeta text-app-texto-secundario hover:border-app-primario hover:bg-app-primario-claro hover:text-app-primario"
      } ${className}`}
      type="button"
      onClick={onClick || noop}
      aria-expanded={expanded}
      aria-label={expanded ? "Contraer" : "Expandir"}
    >
      <ChevronDownIcon
        className={`h-5 w-5 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
      />
    </button>
  );
}
