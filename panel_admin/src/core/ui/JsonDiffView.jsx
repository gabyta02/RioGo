import { diffJsonLines, stringifyJson } from "./jsonDiff";

const lineStyles = {
  left: {
    removed: "bg-app-error-fondo text-red-800",
    unchanged: "text-app-texto-primario",
    empty: "text-transparent",
  },
  right: {
    added: "bg-app-exito-fondo text-emerald-800",
    unchanged: "text-app-texto-primario",
    empty: "text-transparent",
  },
};

function DiffColumn({ title, lines, side }) {
  return (
    <div className="min-w-0 flex-1 overflow-hidden">
      <p className="border-b border-app-borde bg-app-fondo px-3 py-2 text-xs font-black uppercase tracking-wide text-app-texto-secundario">
        {title}
      </p>
      <div className="max-h-72 overflow-auto bg-app-tarjeta p-3 font-mono text-xs font-semibold leading-5">
        {lines.map((line, index) => (
          <div
            key={`${side}-${index}`}
            className="min-h-5 whitespace-pre"
          >
            <span
              className={`inline-block rounded-sm px-1 ${lineStyles[side][line.type] || ""}`}
            >
              {line.text || "\u00A0"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function JsonDiffView({ previous, next }) {
  const oldText = stringifyJson(previous);
  const newText = stringifyJson(next);

  if (!oldText && !newText) {
    return (
      <p className="rounded-lg border border-dashed border-app-borde px-4 py-6 text-center text-sm font-semibold text-app-texto-secundario">
        No hay datos para comparar.
      </p>
    );
  }

  const { left, right } = diffJsonLines(oldText, newText);

  return (
    <div className="overflow-hidden rounded-lg border border-app-borde">
      <div className="grid grid-cols-1 divide-y divide-app-borde lg:grid-cols-[1fr_auto_1fr] lg:divide-x lg:divide-y-0">
        <DiffColumn title="Datos anteriores" lines={left} side="left" />
        <div className="hidden w-px bg-app-borde lg:block" aria-hidden="true" />
        <DiffColumn title="Datos nuevos" lines={right} side="right" />
      </div>
    </div>
  );
}

export function JsonSingleView({ title, value, tone = "added" }) {
  const text = stringifyJson(value);
  if (!text) {
    return (
      <p className="rounded-lg border border-dashed border-app-borde px-4 py-6 text-center text-sm font-semibold text-app-texto-secundario">
        No hay datos para mostrar.
      </p>
    );
  }

  const side = tone === "removed" ? "left" : "right";
  const type = tone === "removed" ? "removed" : "added";
  const lines = text.split("\n").map((line) => ({ text: line, type }));

  return (
    <div className="overflow-hidden rounded-lg border border-app-borde">
      <DiffColumn title={title} lines={lines} side={side} />
    </div>
  );
}
