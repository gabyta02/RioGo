/**
 * Tipografía centralizada del panel administrativo.
 * Usar estas clases en lugar de tamaños sueltos (text-xl, text-base, etc.).
 */
export const fontFamilyClass = "font-sans";

export const text = {
  /** Título de entidad en filas, tarjetas y tablas */
  entityTitle: "text-sm font-black text-app-texto-primario",
  /** Metadatos debajo del título (conteos, IDs, fechas cortas) */
  entityMeta: "text-xs font-semibold text-app-texto-secundario",
  /** Etiqueta de sección dentro de un panel */
  sectionLabel: "text-xs font-black uppercase tracking-wide text-app-texto-secundario",
  /** Texto de cuerpo estándar */
  body: "text-sm font-semibold text-app-texto-primario",
  /** Texto de cuerpo secundario */
  bodyMuted: "text-sm font-semibold text-app-texto-secundario",
  /** Resumen en barra de panel (totales, contadores) */
  panelMeta: "text-sm font-semibold text-app-texto-secundario",
  /** Etiquetas de formulario */
  label: "text-sm font-black text-app-texto-primario",
  /** Mensajes vacíos o de carga */
  empty: "text-sm font-semibold text-app-texto-secundario",
};

export const layout = {
  entityIcon: "grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-app-primario-claro text-app-primario",
  cardPadding: "p-4",
  cardGap: "gap-3",
  rowGap: "gap-3",
};
