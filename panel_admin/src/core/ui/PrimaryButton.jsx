const variants = {
  primary:
    "bg-app-primario text-white shadow-[0_14px_28px_rgba(13,90,56,0.24)] hover:bg-[#0A4B2F]",
  secondary:
    "border border-app-borde bg-app-tarjeta text-app-primario shadow-sm hover:bg-app-primario-claro",
};

export default function PrimaryButton({
  children,
  disabled = false,
  onClick,
  type = "button",
  variant = "primary",
}) {
  return (
    <button
      className={`h-14 w-full rounded-2xl px-5 text-sm font-bold transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro disabled:cursor-not-allowed disabled:opacity-60 ${variants[variant]}`}
      type={type}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}
