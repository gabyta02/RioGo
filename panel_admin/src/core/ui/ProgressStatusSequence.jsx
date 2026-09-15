import { useEffect, useState } from "react";

export default function ProgressStatusSequence({
  active = false,
  className = "",
  intervalMs = 1000,
  steps = [],
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const visibleSteps = steps.filter((step) => step?.id && step?.label);

  useEffect(() => {
    if (!active || visibleSteps.length <= 1) {
      setActiveIndex(0);
      return undefined;
    }

    // Avanza una sola vez por cada estado y se queda en el último mensaje.
    // Evita el efecto visual de carga "en bucle" cuando la consulta tarda más.
    const timer = window.setInterval(() => {
      setActiveIndex((current) => {
        if (current >= visibleSteps.length - 1) {
          window.clearInterval(timer);
          return current;
        }
        return current + 1;
      });
    }, intervalMs);

    return () => window.clearInterval(timer);
  }, [active, intervalMs, visibleSteps.length]);

  if (!active || !visibleSteps.length) {
    return null;
  }

  const activeStep = visibleSteps[activeIndex] || visibleSteps[0];

  return (
    <div
      className={`flex items-center gap-4 rounded-lg border border-app-primario/30 bg-app-primario-claro px-5 py-4 text-base font-black text-app-primario shadow-sm ${className}`}
      role="status"
      aria-live="polite"
    >
      <span className="relative flex h-4 w-4 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-app-primario opacity-30" />
        <span className="relative inline-flex h-4 w-4 rounded-full bg-app-primario" />
      </span>
      <span>{activeStep.label}</span>
    </div>
  );
}
