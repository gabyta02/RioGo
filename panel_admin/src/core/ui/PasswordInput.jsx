import { useState } from "react";
import { EyeIcon } from "./icons";

export default function PasswordInput({
  autoComplete,
  disabled = false,
  icon,
  label,
  name,
  onChange,
  placeholder,
  value,
}) {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <label className="block">
      <span className="sr-only">{label}</span>
      <div className="flex h-14 items-center gap-3 rounded-2xl border border-app-borde bg-app-tarjeta px-4 text-app-texto-secundario shadow-sm transition focus-within:border-app-primario focus-within:ring-4 focus-within:ring-app-primario-claro">
        {icon}
        <input
          className="min-w-0 flex-1 border-0 bg-transparent text-sm font-medium text-app-texto-primario outline-none placeholder:text-app-texto-secundario"
          type={showPassword ? "text" : "password"}
          name={name}
          placeholder={placeholder}
          autoComplete={autoComplete}
          value={value}
          onChange={onChange}
          disabled={disabled}
        />
        <button
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-app-texto-primario transition hover:bg-app-primario-claro hover:text-app-primario focus:outline-none focus:ring-2 focus:ring-app-primario focus:ring-offset-2"
          type="button"
          aria-label={showPassword ? "Ocultar contrasena" : "Mostrar contrasena"}
          onClick={() => setShowPassword((isVisible) => !isVisible)}
          disabled={disabled}
        >
          <EyeIcon visible={showPassword} />
        </button>
      </div>
    </label>
  );
}
