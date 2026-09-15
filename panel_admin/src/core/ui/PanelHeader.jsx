export default function PanelHeader({ eyebrow, title }) {
  return (
    <header>
      <h2 className="text-sm font-bold text-app-texto-primario">{title}</h2>
      {eyebrow ? (
        <p className="mt-1 text-xs font-medium text-app-texto-secundario">{eyebrow}</p>
      ) : null}
    </header>
  );
}
