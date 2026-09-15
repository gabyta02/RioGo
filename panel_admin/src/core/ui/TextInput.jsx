export default function TextInput({
  autoComplete,
  disabled = false,
  icon,
  label,
  name,
  onChange,
  placeholder,
  type = "text",
  value,
}) {
  return (
    <label className="block">
      <span className="sr-only">{label}</span>
      <div className="flex h-14 items-center gap-3 rounded-2xl border border-app-borde bg-app-tarjeta px-4 text-app-texto-secundario shadow-sm transition focus-within:border-app-primario focus-within:ring-4 focus-within:ring-app-primario-claro">
        {icon}
        <input
          className="min-w-0 flex-1 border-0 bg-transparent text-sm font-medium text-app-texto-primario outline-none placeholder:text-app-texto-secundario"
          type={type}
          name={name}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={value}
          onChange={onChange}
          disabled={disabled}
        />
      </div>
    </label>
  );
}
