import { SearchIcon } from "./icons";
import { formInputClass } from "./AdminControls";

const noop = () => {};

export default function SearchBox({ className = "", label, onChange, placeholder, value }) {
  return (
    <label className={`relative block min-w-0 ${className}`}>
      <span className="sr-only">{label}</span>
      <span className="pointer-events-none absolute inset-y-0 left-0 flex w-10 shrink-0 items-center justify-center text-app-texto-secundario">
        <SearchIcon />
      </span>
      <input
        className={`${formInputClass} min-w-0 pl-10`}
        placeholder={placeholder}
        role="searchbox"
        type="text"
        value={value}
        onChange={(event) => (onChange || noop)(event.target.value)}
      />
    </label>
  );
}
