import { useEffect } from "react";
import { FilterIcon, RefreshIcon } from "./icons";
import { text } from "../typography";

const buttonBaseClass =
  "inline-flex items-center justify-center gap-2 rounded-lg text-sm font-black transition focus:outline-none focus:ring-4 disabled:cursor-not-allowed";

const buttonVariants = {
  primary:
    "bg-app-primario text-white hover:bg-app-primario-hover focus:ring-app-primario-claro disabled:opacity-60",
  secondary:
    "border border-app-borde bg-app-tarjeta text-app-texto-primario hover:border-app-primario hover:text-app-primario focus:ring-app-primario-claro disabled:opacity-60",
  danger:
    "border border-app-error-borde bg-app-tarjeta text-app-error hover:border-app-error hover:bg-app-error-fondo focus:ring-app-error-fondo disabled:opacity-50",
};

const noop = () => {};

const alertVariants = {
  error: "border-app-error bg-app-error-fondo text-app-error",
  success: "border-app-exito-borde bg-app-exito-fondo text-app-primario",
  warning: "border-app-acento bg-orange-50 text-app-texto-primario",
};

export const formInputClass =
  "h-10 w-full rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-semibold text-app-texto-primario outline-none transition placeholder:text-app-texto-secundario focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro disabled:cursor-not-allowed disabled:bg-app-fondo disabled:text-app-texto-secundario";

export const formTextareaClass =
  "w-full resize-y rounded-lg border border-app-borde bg-app-tarjeta px-3 py-2 text-sm font-semibold text-app-texto-primario outline-none transition placeholder:text-app-texto-secundario focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro disabled:cursor-not-allowed disabled:bg-app-fondo disabled:text-app-texto-secundario";

export function TimedAlert({
  children,
  className = "",
  duration = 5000,
  onDismiss,
  variant = "error",
}) {
  useEffect(() => {
    if (!children || !onDismiss) {
      return undefined;
    }

    const timer = window.setTimeout(onDismiss, duration);
    return () => window.clearTimeout(timer);
  }, [children, duration, onDismiss]);

  if (!children) {
    return null;
  }

  return (
    <div
      className={`rounded-lg border p-3 text-sm font-bold ${alertVariants[variant]} ${className}`}
      role="status"
    >
      {children}
    </div>
  );
}

export function FormField({ children, label }) {
  return (
    <label className="block">
      <span className={text.label}>{label}</span>
      <div className="mt-2">{children}</div>
    </label>
  );
}

export function Toggle({ checked, disabled = false, label, onChange }) {
  return (
    <button
      className={`flex h-7 w-12 items-center rounded-full p-1 transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro disabled:cursor-not-allowed disabled:opacity-60 ${
        checked ? "bg-app-primario-interactivo" : "bg-app-borde"
      }`}
      type="button"
      onClick={() => onChange?.(!checked)}
      disabled={disabled}
      aria-label={label}
      aria-pressed={checked}
    >
      <span
        className={`h-5 w-5 rounded-full bg-white shadow transition ${
          checked ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

export function ToggleRow({ checked, children, onChange }) {
  return (
    <div className="flex min-h-12 items-center justify-between gap-4 rounded-lg border border-app-borde px-4 py-2">
      <span className={text.label}>{children}</span>
      <Toggle checked={checked} label={children} onChange={onChange} />
    </div>
  );
}

export function ChipButton({ active = false, children, onClick }) {
  return (
    <button
      className={`h-9 rounded-lg border px-3 text-sm font-black transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro ${
        active
          ? "border-app-primario bg-app-primario text-white"
          : "border-app-borde bg-app-tarjeta text-app-texto-secundario hover:border-app-primario hover:text-app-primario"
      }`}
      type="button"
      onClick={onClick || noop}
    >
      {children}
    </button>
  );
}

export function TabButton({ active = false, children, onClick }) {
  return (
    <button
      className={`h-9 rounded-lg px-3 text-sm font-black transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro ${
        active
          ? "border-2 border-app-primario-interactivo bg-app-primario-claro text-app-texto-primario shadow-[0_0_0_2px_rgba(0,135,111,0.12)]"
          : "text-app-texto-secundario hover:bg-app-fondo hover:text-app-texto-primario"
      }`}
      type="button"
      onClick={onClick || noop}
    >
      {children}
    </button>
  );
}

export function AdminActionButton({
  children,
  className = "",
  disabled = false,
  icon,
  onClick,
  type = "button",
  variant = "secondary",
}) {
  return (
    <button
      className={`${buttonBaseClass} h-10 px-4 ${buttonVariants[variant]} ${className}`}
      type={type}
      onClick={onClick || noop}
      disabled={disabled}
    >
      {icon}
      {children}
    </button>
  );
}

export function TableActionButton({
  children,
  className = "",
  disabled = false,
  icon,
  onClick,
  type = "button",
  variant = "secondary",
}) {
  return (
    <button
      className={`${buttonBaseClass} h-10 px-3 ${buttonVariants[variant]} ${className}`}
      type={type}
      onClick={onClick || noop}
      disabled={disabled}
    >
      {icon}
      {children}
    </button>
  );
}

export function DashboardDateFilters({
  disabled = false,
  filters,
  onApply,
  onChange,
  onClear,
}) {
  const periodOptions = [
    { value: "today", label: "Hoy" },
    { value: "week", label: "Semana" },
    { value: "month", label: "Mes" },
    { value: "year", label: "Año" },
    { value: "all", label: "Todo" },
    { value: "custom", label: "Personalizado" },
  ];

  const isCustom = filters.periodo === "custom";

  return (
    <div className="rounded-xl border border-app-borde bg-app-tarjeta p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[260px] flex-1">
          <span className="text-xs font-black uppercase tracking-[0.12em] text-app-texto-secundario">
            Período
          </span>
          <div className="mt-2 flex flex-wrap gap-2">
            {periodOptions.map((option) => (
              <button
                key={option.value}
                className={`h-9 rounded-lg border px-3 text-sm font-black transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro disabled:cursor-not-allowed disabled:opacity-60 ${
                  filters.periodo === option.value
                    ? "border-app-primario bg-app-primario text-white"
                    : "border-app-borde bg-app-fondo text-app-texto-secundario hover:border-app-primario hover:text-app-primario"
                }`}
                type="button"
                onClick={() => onChange({ ...filters, periodo: option.value })}
                disabled={disabled}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {isCustom ? (
          <>
            <label className="block min-w-[170px]">
              <span className="text-xs font-black text-app-texto-secundario">Fecha inicio</span>
              <input
                className={`${formInputClass} mt-2`}
                type="date"
                value={filters.fecha_inicio}
                onChange={(event) => onChange({ ...filters, fecha_inicio: event.target.value })}
                disabled={disabled}
              />
            </label>
            <label className="block min-w-[170px]">
              <span className="text-xs font-black text-app-texto-secundario">Fecha fin</span>
              <input
                className={`${formInputClass} mt-2`}
                type="date"
                value={filters.fecha_fin}
                onChange={(event) => onChange({ ...filters, fecha_fin: event.target.value })}
                disabled={disabled}
              />
            </label>
          </>
        ) : null}

        <AdminActionButton
          icon={<FilterIcon />}
          onClick={onApply}
          disabled={disabled || (isCustom && (!filters.fecha_inicio || !filters.fecha_fin))}
          variant="primary"
        >
          Aplicar filtros
        </AdminActionButton>
        <AdminActionButton icon={<RefreshIcon />} onClick={onClear} disabled={disabled}>
          Limpiar
        </AdminActionButton>
      </div>
    </div>
  );
}

export function SelectFilter({ icon = false, label, options, value, onChange }) {
  return (
    <label className="relative block min-w-0">
      <span className="sr-only">{label}</span>
      {icon ? (
        <span className="pointer-events-none absolute left-3 top-1/2 grid h-5 w-5 -translate-y-1/2 place-items-center text-app-texto-secundario">
          <FilterIcon />
        </span>
      ) : null}
      <select
        className={`h-10 w-full min-w-0 rounded-lg border border-app-borde bg-app-tarjeta pr-8 text-sm font-semibold text-app-texto-secundario outline-none transition focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro sm:min-w-[150px] ${
          icon ? "pl-10" : "pl-3"
        }`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
