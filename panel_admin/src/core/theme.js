/**
 * Fuente única de colores y tokens visuales del panel administrativo.
 * Tailwind los consume desde tailwind.config.js.
 */
export const appColors = {
  primario: "#0D5A38",
  "primario-hover": "#0B4B30",
  "primario-claro": "#EAF4EF",
  "primario-interactivo": "#00876F",
  fondo: "#F9FAFB",
  acento: "#FF7A00",
  tarjeta: "#FFFFFF",
  error: "#EF4444",
  "error-fondo": "#FEF2F2",
  "error-borde": "#FECACA",
  exito: "#10B981",
  "exito-fondo": "#ECFDF5",
  "exito-borde": "#A7F3D0",
  "texto-primario": "#1E293B",
  "texto-secundario": "#64748B",
  borde: "#E2E8F0",
  "notificacion-fondo": "#F1E9D8",
  cuerpo: "#F7F8FA",
  menu: {
    fondo: "#F9F9F5",
    activo: "#C8DDD2",
    primario: "#004D40",
    texto: "#64748B",
    inactivo: "#94A3B8",
    sage: "#6F9488",
    borde: "#E8ECE9",
  },
};

export const controlTokens = {
  height: "2.5rem",
  heightCompact: "2.25rem",
  fontSize: "0.875rem",
  fontSizeSm: "0.75rem",
  radius: "0.5rem",
};

/** Tipografía: clases reutilizables en src/core/typography.js */
export const fontFamily =
  'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
