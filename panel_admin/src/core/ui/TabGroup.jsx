const noop = () => {};

export default function TabGroup({ activeId, onChange, tabs }) {
  return (
    <div className="flex flex-wrap gap-2 border-b border-app-borde">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`rounded-t-lg border px-4 py-2.5 text-sm font-black transition ${
            activeId === tab.id
              ? "border-app-borde border-b-white bg-app-tarjeta text-app-primario"
              : "border-transparent text-app-texto-secundario hover:text-app-primario"
          }`}
          type="button"
          onClick={() => (onChange || noop)(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
