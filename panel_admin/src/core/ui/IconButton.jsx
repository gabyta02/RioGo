const noop = () => {};

export default function IconButton({ children, label, onClick, type = "button" }) {
  return (
    <button
      className="grid h-10 w-10 place-items-center rounded-lg border border-app-borde bg-app-tarjeta text-app-texto-secundario transition hover:border-app-primario hover:bg-app-primario-claro hover:text-app-primario focus:outline-none focus:ring-4 focus:ring-app-primario-claro"
      type={type}
      onClick={onClick || noop}
      aria-label={label}
      title={label}
    >
      {children}
    </button>
  );
}
