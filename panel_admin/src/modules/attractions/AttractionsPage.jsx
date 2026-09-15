import { useEffect, useMemo, useRef, useState } from "react";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import Panel from "../../core/ui/Panel";
import {
  AdminActionButton,
  ChipButton,
  FormField,
  SelectFilter,
  TabButton,
  TableActionButton,
  TimedAlert,
  ToggleRow,
  formInputClass,
  formTextareaClass,
} from "../../core/ui/AdminControls";
import Pagination from "../../core/ui/Pagination";
import SearchBox from "../../core/ui/SearchBox";
import { EditIcon, PlusIcon, TrashIcon } from "../../core/ui/icons";
import {
  actualizarAtractivo,
  cambiarEstadoAtractivo,
  crearAtractivo,
  eliminarAtractivo,
  obtenerAtractivos,
  obtenerCatalogosAtractivos,
  obtenerDetalleAtractivo,
  subirImagenesAtractivo,
} from "./attractionsService";
import { getApiErrorMessage } from "../../core/api/errors";
import { obtenerSesion, sinSitiosAsignados, tieneAccion } from "../../core/auth/authStorage";

const logoSrc = `${import.meta.env.BASE_URL}assets/logo.png`;
const riobambaCoords = { latitud: "-1.6635", longitud: "-78.6546" };

const estadoOptions = [
  { value: "all", label: "Estado" },
  { value: "activo", label: "Activo" },
  { value: "inactivo", label: "Inactivo" },
];

const servicioOptions = [
  { value: "all", label: "Servicios" },
  { value: "wifi", label: "WiFi" },
  { value: "parqueadero", label: "Parqueadero" },
  { value: "mascotas", label: "Mascotas" },
  { value: "accesibilidad", label: "Accesibilidad" },
];

const precioOptions = [
  { value: "all", label: "Precio" },
  { value: "gratis", label: "Gratis" },
  { value: "pagado", label: "Pagado" },
];

const siteTypeOptions = [
  { value: "servicio_turistico", label: "Servicio turístico" },
  { value: "atractivo_turistico", label: "Atractivo turístico" },
  { value: "operadora_turistica", label: "Operadora turística" },
  { value: "desconocido", label: "Desconocido" },
];

const tabs = [
  { id: "general", label: "General" },
  { id: "clasificacion", label: "Clasificación" },
  { id: "ubicacion", label: "Ubicación" },
  { id: "horarios", label: "Horarios" },
  { id: "servicios", label: "Servicios" },
  { id: "contacto", label: "Contacto" },
  { id: "imagenes", label: "Imágenes" },
  { id: "precios", label: "Precios" },
];

const days = [
  { value: 1, label: "Lunes" },
  { value: 2, label: "Martes" },
  { value: 3, label: "Miércoles" },
  { value: 4, label: "Jueves" },
  { value: 5, label: "Viernes" },
  { value: 6, label: "Sábado" },
  { value: 7, label: "Domingo" },
];

const initialDayTurno = { hora_inicio: "07:00", hora_fin: "17:00" };
const initialDaySchedule = { cerrado: false, turnos: [{ ...initialDayTurno }] };

function buildEmptyHorariosPorDia() {
  return Object.fromEntries(days.map((d) => [d.value, { ...initialDaySchedule, turnos: [{ ...initialDayTurno }] }]));
}

const initialForm = {
  nombre: "",
  tipo: "atractivo_turistico",
  descripcion_corta: "",
  id_categoria: "",
  id_subcategoria: "",
  id_parroquia: "",
  id_plataforma: "",
  direccion_texto: "",
  referencia_adicional: "",
  latitud: riobambaCoords.latitud,
  longitud: riobambaCoords.longitud,
  abierto_24h: false,
  hora_inicio: "07:00",
  hora_fin: "17:00",
  dias_semana: [],
  horarios_por_dia: buildEmptyHorariosPorDia(),
  comentario_horario: "",
  tiene_wifi: true,
  parqueadero: true,
  permite_mascotas: false,
  accesibilidad: true,
  contactos: [],
  imagenes: [],
  imagen_url_input: "",
  es_gratuito: true,
  precio_min: "",
  precio_max: "",
  etiqueta_precio: "desconocido",
  tarifa_acceso: "",
  condicion_tarifa: "",
};

function buildHorariosPorDiaFromSite(site) {
  const mapa = buildEmptyHorariosPorDia();
  const detalles = Array.isArray(site.horario?.detalles) ? site.horario.detalles : [];
  if (detalles.length) {
    detalles.forEach((item) => {
      if (item.dia_semana >= 1 && item.dia_semana <= 7) {
        if (item.cerrado) {
          mapa[item.dia_semana] = { cerrado: true, turnos: [] };
        } else {
          if (!mapa[item.dia_semana].turnos.find((t) => t.hora_inicio === (item.hora_inicio || site.horario?.hora_inicio || "07:00") && t.hora_fin === (item.hora_fin || site.horario?.hora_fin || "17:00"))) {
            mapa[item.dia_semana].turnos.push({
              hora_inicio: item.hora_inicio || site.horario?.hora_inicio || "07:00",
              hora_fin: item.hora_fin || site.horario?.hora_fin || "17:00",
            });
          }
        }
      }
    });
    detalles.forEach((item) => {
      if (item.dia_semana >= 1 && item.dia_semana <= 7 && item.cerrado) {
        mapa[item.dia_semana].cerrado = true;
        mapa[item.dia_semana].turnos = [];
      }
    });
  } else if (!site.horario?.abierto_24h) {
    const hi = site.horario?.hora_inicio || "07:00";
    const hf = site.horario?.hora_fin || "17:00";
    (site.horario?.dias_semana || []).forEach((d) => {
      if (d >= 1 && d <= 7) {
        mapa[d] = { cerrado: false, turnos: [{ hora_inicio: hi, hora_fin: hf }] };
      }
    });
  }
  return mapa;
}

function buildInitialForm(site) {
  if (!site) return initialForm;

  return {
    nombre: site.nombre || "",
    tipo: site.tipo || "atractivo_turistico",
    descripcion_corta: site.descripcion_corta || "",
    id_categoria: site.id_categoria ? String(site.id_categoria) : "",
    id_subcategoria: site.id_subcategoria ? String(site.id_subcategoria) : "",
    id_parroquia: site.id_parroquia ? String(site.id_parroquia) : "",
    id_plataforma: site.id_plataforma ? String(site.id_plataforma) : "",
    direccion_texto: site.direccion?.direccion_texto || "",
    referencia_adicional: site.direccion?.referencia_adicional || "",
    latitud: site.direccion?.latitud != null ? String(site.direccion.latitud) : riobambaCoords.latitud,
    longitud: site.direccion?.longitud != null ? String(site.direccion.longitud) : riobambaCoords.longitud,
    abierto_24h: Boolean(site.horario?.abierto_24h),
    hora_inicio: site.horario?.abierto_24h ? "" : site.horario?.hora_inicio || "07:00",
    hora_fin: site.horario?.abierto_24h ? "" : site.horario?.hora_fin || "17:00",
    dias_semana: site.horario?.dias_semana || [],
    horarios_por_dia: buildHorariosPorDiaFromSite(site),
    comentario_horario: site.horario?.comentario || "",
    tiene_wifi: Boolean(site.tiene_wifi),
    parqueadero: Boolean(site.parqueadero),
    permite_mascotas: Boolean(site.permite_mascotas),
    accesibilidad: Boolean(site.accesibilidad),
    contactos: (site.contactos || []).map((contact) => ({
      nombre: contact.nombre || "",
      contenido: contact.contenido || "",
    })),
    imagenes: (site.multimedia || []).map((item) => ({ ...item, eliminada: false })),
    imagen_url_input: "",
    es_gratuito: Boolean(site.precio?.es_gratuito),
    precio_min: site.precio?.precio_min != null ? String(site.precio.precio_min) : "",
    precio_max: site.precio?.precio_max != null ? String(site.precio.precio_max) : "",
    etiqueta_precio: site.precio?.etiqueta_precio || "desconocido",
    tarifa_acceso: site.precio?.tarifa_acceso != null ? String(site.precio.tarifa_acceso) : "",
    condicion_tarifa: site.precio?.condicion_tarifa || "",
  };
}

function StatusBadge({ active }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-black ${
        active
          ? "border-emerald-200 bg-emerald-50 text-app-primario"
          : "border-slate-200 bg-slate-100 text-app-texto-secundario"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-app-exito" : "bg-app-texto-secundario"}`} />
      {active ? "Activo" : "Inactivo"}
    </span>
  );
}

function ensureMapLibre() {
  if (!document.getElementById("maplibre-css")) {
    const link = document.createElement("link");
    link.id = "maplibre-css";
    link.rel = "stylesheet";
    link.href = "https://unpkg.com/maplibre-gl/dist/maplibre-gl.css";
    document.head.appendChild(link);
  }

  if (window.maplibregl) {
    return Promise.resolve(window.maplibregl);
  }

  return new Promise((resolve, reject) => {
    const existing = document.getElementById("maplibre-js");
    if (existing) {
      existing.addEventListener("load", () => resolve(window.maplibregl));
      existing.addEventListener("error", reject);
      return;
    }

    const script = document.createElement("script");
    script.id = "maplibre-js";
    script.src = "https://unpkg.com/maplibre-gl/dist/maplibre-gl.js";
    script.onload = () => resolve(window.maplibregl);
    script.onerror = reject;
    document.body.appendChild(script);
  });
}

function LocationMap({ latitud, longitud, onChange }) {
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    let disposed = false;

    ensureMapLibre()
      .then((maplibregl) => {
        if (disposed || !containerRef.current) return;
        const center = [Number(longitud) || Number(riobambaCoords.longitud), Number(latitud) || Number(riobambaCoords.latitud)];
        const map = new maplibregl.Map({
          container: containerRef.current,
          style: "https://tiles.openfreemap.org/styles/liberty",
          center,
          zoom: 13,
        });
        const marker = new maplibregl.Marker({ color: "#00876F" }).setLngLat(center).addTo(map);

        map.on("click", (event) => {
          marker.setLngLat([event.lngLat.lng, event.lngLat.lat]);
          onChange({
            latitud: event.lngLat.lat.toFixed(6),
            longitud: event.lngLat.lng.toFixed(6),
          });
        });

        mapRef.current = map;
        markerRef.current = marker;
      })
      .catch(() => {});

    return () => {
      disposed = true;
      mapRef.current?.remove();
    };
  }, []);

  useEffect(() => {
    const lng = Number(longitud);
    const lat = Number(latitud);
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) return;
    markerRef.current?.setLngLat([lng, lat]);
    mapRef.current?.setCenter([lng, lat]);
  }, [latitud, longitud]);

  return (
    <div className="relative h-[184px] overflow-hidden rounded-lg border border-app-borde bg-app-primario-claro">
      <div ref={containerRef} className="h-full w-full" />
      <span className="pointer-events-none absolute bottom-3 left-3 rounded bg-white/90 px-2 py-1 text-xs font-bold text-app-texto-secundario shadow-sm">
        Ubicacion del atractivo
      </span>
    </div>
  );
}

function MobilePreview({ form, categoryName }) {
  const principal = form.imagenes.find((item) => item.es_principal) || form.imagenes[0];
  const firstDay = form.dias_semana[0];
  const firstSchedule = firstDay ? form.horarios_por_dia[firstDay] : null;
  const scheduleText = form.abierto_24h
    ? "Abierto 24 horas"
    : firstSchedule && !firstSchedule.cerrado && firstSchedule.turnos && firstSchedule.turnos.length > 0
      ? firstSchedule.turnos.map((t) => `${t.hora_inicio} - ${t.hora_fin}`).join(" / ")
      : "Cerrado";

  const precioText = form.es_gratuito
    ? "$ Gratuito"
    : form.tarifa_acceso
      ? `$ ${form.tarifa_acceso}`
      : `$ ${form.precio_min || "0"} - ${form.precio_max || "0"}`;

  return (
    <aside className="w-full max-w-[280px]">
      <p className="mb-2 text-xs font-black uppercase text-app-texto-secundario">Vista previa en la app</p>
      <div className="rounded-2xl border-[5px] border-[#40514D] bg-white p-3 shadow-lg">
        <div className="relative h-32 overflow-hidden rounded-lg bg-app-primario-claro">
          <img
            className="h-full w-full object-cover"
            src={principal?.url || logoSrc}
            alt=""
            onError={(event) => {
              event.currentTarget.src = logoSrc;
            }}
          />
          <span className="absolute left-2 top-2 rounded-full bg-app-primario px-2 py-1 text-[10px] font-black text-white">
            {categoryName || "Categoria"}
          </span>
        </div>
        <div className="p-2">
          <h3 className="truncate text-sm font-black text-app-texto-primario">
            {form.nombre || "Nombre del atractivo"}
          </h3>
          <p className="mt-2 truncate text-xs font-semibold text-app-texto-secundario">
            {form.direccion_texto || "Dirección del atractivo"}
          </p>
          <p className="mt-2 text-xs font-semibold text-app-texto-secundario">{scheduleText}</p>
          <p className="mt-2 text-xs font-black text-app-primario">
            {precioText}
          </p>
          <button className="mt-3 h-9 w-full rounded-lg bg-[#00876F] text-xs font-black text-white" type="button">
            Ver mas
          </button>
        </div>
      </div>
      <p className="mt-2 text-center text-xs font-semibold text-app-texto-secundario">Asi se mostrara en el movil</p>
    </aside>
  );
}

function AttractionFormModal({ catalogos, onClose, onSaved, setGlobalError, site }) {
  const [activeTab, setActiveTab] = useState("general");
  const [form, setForm] = useState(() => buildInitialForm(site));
  const [isSaving, setIsSaving] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [localError, setLocalError] = useState("");
  const [mostrarHorarioPorDia, setMostrarHorarioPorDia] = useState(false);

  const categoriaOptions = useMemo(
    () => catalogos.categorias.map((item) => ({ value: String(item.id_categoria), label: item.nombre })),
    [catalogos.categorias],
  );

  const subcategoriaOptions = useMemo(
    () =>
      catalogos.subcategorias
        .filter((item) => !form.id_categoria || String(item.id_categoria) === form.id_categoria)
        .map((item) => ({ value: String(item.id_subcategoria), label: item.nombre })),
    [catalogos.subcategorias, form.id_categoria],
  );

  const plataformaOptions = useMemo(
    () =>
      catalogos.plataformas
        .filter((item) => !form.id_parroquia || String(item.id_parroquia || "") === form.id_parroquia)
        .map((item) => ({ value: String(item.id), label: item.nombre })),
    [catalogos.plataformas, form.id_parroquia],
  );

  const selectedCategoryName =
    catalogos.categorias.find((item) => String(item.id_categoria) === form.id_categoria)?.nombre || "";
  const isEdit = Boolean(site);

  function updateField(key, value) {
    setLocalError("");
    setForm((current) => {
      const next = { ...current, [key]: value };
      if (key === "id_categoria") next.id_subcategoria = "";
      if (key === "id_parroquia") next.id_plataforma = "";
      if (key === "abierto_24h") {
        if (value) {
          next.hora_inicio = "";
          next.hora_fin = "";
        } else {
          next.hora_inicio = current.hora_inicio || "07:00";
          next.hora_fin = current.hora_fin || "17:00";
        }
      }
      if (key === "es_gratuito" && value) {
        next.precio_min = "";
        next.precio_max = "";
        next.etiqueta_precio = "desconocido";
        next.tarifa_acceso = "";
        next.condicion_tarifa = "";
      }
      if (!next.es_gratuito) {
        if (key === "tarifa_acceso" && String(value).trim()) {
          next.precio_min = "";
          next.precio_max = "";
          next.etiqueta_precio = "desconocido";
        } else if (key === "precio_min" || key === "precio_max") {
          if (String(value).trim()) {
            next.tarifa_acceso = "";
            next.condicion_tarifa = "";
          }
        }
      }
      return next;
    });
  }

  function updateDaySchedule(day, partial) {
    setLocalError("");
    setForm((current) => {
      const mapa = { ...current.horarios_por_dia };
      const prev = mapa[day] || initialDaySchedule;
      if (partial.cerrado !== undefined) {
        mapa[day] = { ...prev, cerrado: partial.cerrado };
      } else if (partial.addTurno !== undefined) {
        mapa[day] = {
          ...prev,
          turnos: [...prev.turnos, { hora_inicio: "12:00", hora_fin: "18:00" }],
        };
      } else if (partial.removeTurno !== undefined) {
        mapa[day] = {
          ...prev,
          turnos: prev.turnos.filter((_, i) => i !== partial.removeTurno),
        };
      } else if (partial.updateTurno !== undefined) {
        mapa[day] = {
          ...prev,
          turnos: prev.turnos.map((t, i) =>
            i === partial.updateTurno.index ? { ...t, ...partial.updateTurno.data } : t
          ),
        };
      }
      return { ...current, horarios_por_dia: mapa };
    });
  }

  function addContact() {
    setLocalError("");
    setForm((current) => ({
      ...current,
      contactos: [...current.contactos, { nombre: "", contenido: "" }],
    }));
  }

  function updateContact(index, field, value) {
    setLocalError("");
    setForm((current) => ({
      ...current,
      contactos: current.contactos.map((c, i) => (i === index ? { ...c, [field]: value } : c)),
    }));
  }

  function removeContact(index) {
    setLocalError("");
    setForm((current) => ({
      ...current,
      contactos: current.contactos.filter((_, i) => i !== index),
    }));
  }

  function toggleDay(day) {
    setLocalError("");
    setForm((current) => {
      const mapa = { ...current.horarios_por_dia };
      if (current.dias_semana.includes(day)) {
        return {
          ...current,
          dias_semana: current.dias_semana.filter((item) => item !== day),
        };
      }
      mapa[day] = { ...initialDaySchedule };
      return {
        ...current,
        dias_semana: [...current.dias_semana, day].sort((a, b) => a - b),
        horarios_por_dia: mapa,
      };
    });
  }

  function addImageUrl() {
    const url = form.imagen_url_input.trim();
    if (!url) return;
    setLocalError("");
    setForm((current) => ({
      ...current,
      imagen_url_input: "",
      imagenes: [
        ...current.imagenes,
        {
          url,
          es_principal: current.imagenes.filter((item) => !item.eliminada).length === 0,
          eliminada: false,
        },
      ],
    }));
  }

  async function handleUpload(event) {
    const files = event.target.files;
    if (!files?.length) return;
    if (!form.nombre.trim()) {
      setLocalError("Primero ingresa el nombre del atractivo para subir imágenes");
      event.target.value = "";
      return;
    }

    setIsUploading(true);
    setLocalError("");
    try {
      const uploaded = await subirImagenesAtractivo(form.nombre.trim(), files);
      setForm((current) => ({
        ...current,
        imagenes: [
          ...current.imagenes,
          ...uploaded.map((item, index) => ({
            url: item.url,
            es_principal: current.imagenes.filter((image) => !image.eliminada).length === 0 && index === 0,
            eliminada: false,
          })),
        ],
      }));
    } catch (err) {
      setLocalError(getApiErrorMessage(err, "No se pudieron cargar los atractivos"));
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  function setPrincipalImage(index) {
    setLocalError("");
    setForm((current) => ({
      ...current,
      imagenes: current.imagenes.map((item, itemIndex) => ({
        ...item,
        es_principal: !item.eliminada && itemIndex === index,
      })),
    }));
  }

  function removeImage(index) {
    setLocalError("");
    setForm((current) => {
      const imagenes = current.imagenes.map((item, itemIndex) => (
        itemIndex === index ? { ...item, eliminada: !item.eliminada, es_principal: false } : item
      ));
      const activeImages = imagenes.filter((item) => !item.eliminada);
      if (activeImages.length && !activeImages.some((item) => item.es_principal)) {
        const firstActiveIndex = imagenes.findIndex((item) => !item.eliminada);
        imagenes[firstActiveIndex] = { ...imagenes[firstActiveIndex], es_principal: true };
      }
      return { ...current, imagenes };
    });
  }

  function validateForm() {
    const required = [
      ["nombre", "Nombre del atractivo"],
      ["tipo", "Tipo"],
      ["descripcion_corta", "Descripción"],
      ["id_categoria", "Categoría"],
      ["id_subcategoria", "Subcategoría"],
      ["direccion_texto", "Dirección"],
      ["referencia_adicional", "Referencia"],
      ["latitud", "Latitud"],
      ["longitud", "Longitud"],
    ];
    const missing = required.find(([key]) => !String(form[key] || "").trim());
    if (missing) return `Completa el campo: ${missing[1]}`;
    const tieneComentarioHorario = Boolean(form.comentario_horario.trim());
    if (!form.dias_semana.length && !form.abierto_24h && !tieneComentarioHorario) {
      return "Marca al menos un día de atención, activa 24 horas o agrega un comentario";
    }
    if (!form.abierto_24h) {
      for (const day of form.dias_semana) {
        const schedule = form.horarios_por_dia[day];
        if (!schedule) return `Falta horario para el día ${day}`;
        if (!schedule.cerrado) {
          if (!schedule.turnos || schedule.turnos.length === 0) {
            return `Agrega al menos un horario para el día ${day}`;
          }
          for (let i = 0; i < schedule.turnos.length; i++) {
            const turno = schedule.turnos[i];
            if (!turno.hora_inicio || !turno.hora_fin) {
              return `Completa la hora de inicio y fin para el turno ${i + 1} del día ${day}`;
            }
            if (turno.hora_inicio >= turno.hora_fin) {
              return `La hora de inicio debe ser menor que la de fin en el turno ${i + 1} del día ${day}`;
            }
          }
        }
      }
    }
    if (!form.imagenes.filter((item) => !item.eliminada).length) {
      return "Agrega al menos una imagen antes de guardar";
    }
    const validContacts = form.contactos.filter((c) => c.nombre.trim() && c.contenido.trim());
    if (!validContacts.length) return "Agrega al menos un contacto con nombre y contenido";
    if (!form.es_gratuito) {
      const tieneRango = String(form.precio_min).trim() || String(form.precio_max).trim();
      const tieneTarifa = String(form.tarifa_acceso).trim();
      if (tieneRango && tieneTarifa) {
        return "Elige rango de precio o tarifa de acceso, no ambos";
      }
      if (!tieneRango && !tieneTarifa) {
        return "Define un rango de precio o una tarifa de acceso";
      }
      if (tieneRango) {
        if (!String(form.precio_min).trim() || !String(form.precio_max).trim()) {
          return "Completa precio mínimo y máximo";
        }
        if (Number(form.precio_min) > Number(form.precio_max)) {
          return "El precio mínimo no puede ser mayor que el máximo";
        }
      }
    }
    if (!Number.isFinite(Number(form.latitud)) || !Number.isFinite(Number(form.longitud))) {
      return "Latitud y longitud deben ser números válidos";
    }
    return "";
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const validationError = validateForm();
    if (validationError) {
      setLocalError(validationError);
      return;
    }

    setIsSaving(true);
    setLocalError("");
    setGlobalError("");

    try {
      const tieneDetallesPorDia = !form.abierto_24h;
      const detallesPayload = form.abierto_24h
        ? []
        : form.dias_semana.flatMap((day) => {
            const schedule = form.horarios_por_dia[day] || initialDaySchedule;
            if (schedule.cerrado) {
              return [{ dia_semana: day, cerrado: true, hora_inicio: null, hora_fin: null }];
            }
            return schedule.turnos.map((turno) => ({
              dia_semana: day,
              cerrado: false,
              hora_inicio: turno.hora_inicio || null,
              hora_fin: turno.hora_fin || null,
            }));
          });

      const precio = { es_gratuito: form.es_gratuito };
      if (!form.es_gratuito) {
        const tieneRango =
          String(form.precio_min).trim() && String(form.precio_max).trim();
        const tieneTarifa = String(form.tarifa_acceso).trim();
        if (tieneRango) {
          precio.precio_min = Number(form.precio_min);
          precio.precio_max = Number(form.precio_max);
          precio.etiqueta_precio = form.etiqueta_precio || "desconocido";
        } else if (tieneTarifa) {
          precio.tarifa_acceso = Number(form.tarifa_acceso);
          if (form.condicion_tarifa.trim()) {
            precio.condicion_tarifa = form.condicion_tarifa.trim();
          }
        }
      }

      const payload = {
        id_parroquia: form.id_parroquia ? Number(form.id_parroquia) : null,
        id_plataforma: form.id_plataforma ? Number(form.id_plataforma) : null,
        id_categoria: Number(form.id_categoria),
        id_subcategoria: Number(form.id_subcategoria),
        tipo: form.tipo,
        nombre: form.nombre.trim(),
        descripcion_corta: form.descripcion_corta.trim(),
        direccion_texto: form.direccion_texto.trim(),
        referencia_adicional: form.referencia_adicional.trim(),
        latitud: Number(form.latitud),
        longitud: Number(form.longitud),
        permite_mascotas: form.permite_mascotas,
        parqueadero: form.parqueadero,
        tiene_wifi: form.tiene_wifi,
        accesibilidad: form.accesibilidad,
        activo: true,
        horario: {
          abierto_24h: form.abierto_24h,
          dias_semana: form.dias_semana,
          hora_inicio: tieneDetallesPorDia ? null : form.hora_inicio || null,
          hora_fin: tieneDetallesPorDia ? null : form.hora_fin || null,
          comentario: form.comentario_horario.trim() || null,
          detalles: detallesPayload,
        },
        contactos: form.contactos
          .filter((c) => c.nombre.trim() && c.contenido.trim())
          .map((c) => ({
            nombre: c.nombre.trim(),
            contenido: c.contenido.trim(),
          })),
        multimedia: form.imagenes
          .filter((item) => !item.eliminada)
          .map(({ eliminada, ...item }) => item),
        precio,
      };
      if (isEdit) {
        await actualizarAtractivo(site.id_sitio, payload);
      } else {
        await crearAtractivo(payload);
      }
      onSaved();
    } catch (err) {
      setLocalError(getApiErrorMessage(err, "No se pudieron cargar los atractivos"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/30 p-4">
      <form className="min-h-[560px] w-full max-w-5xl overflow-hidden rounded-lg bg-app-tarjeta shadow-2xl" onSubmit={handleSubmit}>
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            <h2 className="text-lg font-black text-app-texto-primario">{isEdit ? "Editar atractivo turístico" : "Nuevo atractivo turístico"}</h2>
            <p className="mt-1 text-sm font-semibold text-app-texto-secundario">Completa los datos del atractivo.</p>
          </div>
          <button className="grid h-8 w-8 place-items-center rounded-lg text-xl leading-none text-app-texto-primario transition hover:bg-app-fondo" type="button" onClick={onClose} aria-label="Cerrar">
            x
          </button>
        </div>

        <div className="mt-5 flex flex-wrap gap-2 px-5">
          {tabs.map((tab) => (
            <TabButton
              key={tab.id}
              active={activeTab === tab.id}
              onClick={() => {
                setLocalError("");
                setActiveTab(tab.id);
              }}
            >
              {tab.label}
            </TabButton>
          ))}
        </div>

        <div className="grid gap-8 px-5 py-5 lg:grid-cols-[minmax(0,1fr)_280px]">
          <div className="space-y-4">
            <TimedAlert onDismiss={() => setLocalError("")}>{localError}</TimedAlert>

            {activeTab === "general" ? (
              <>
                <FormField label="Nombre del atractivo">
                  <input className={formInputClass} required maxLength={180} value={form.nombre} onChange={(event) => updateField("nombre", event.target.value)} />
                </FormField>
                <FormField label="Tipo">
                  <select className={formInputClass} required value={form.tipo} onChange={(event) => updateField("tipo", event.target.value)}>
                    {siteTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>{option.label}</option>
                    ))}
                  </select>
                </FormField>
                <FormField label="Descripción">
                  <textarea className={`${formTextareaClass} min-h-[150px]`} required maxLength={350} value={form.descripcion_corta} onChange={(event) => updateField("descripcion_corta", event.target.value)} />
                </FormField>
              </>
            ) : null}

            {activeTab === "clasificacion" ? (
              <div className="max-w-sm space-y-4">
                <FormField label="Categoría">
                  <select className={formInputClass} required value={form.id_categoria} onChange={(event) => updateField("id_categoria", event.target.value)}>
                    <option value="">Seleccionar categoría</option>
                    {categoriaOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </FormField>
                <FormField label="Subcategoría">
                  <select className={formInputClass} required value={form.id_subcategoria} onChange={(event) => updateField("id_subcategoria", event.target.value)}>
                    <option value="">Seleccionar subcategoría</option>
                    {subcategoriaOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </FormField>
              </div>
            ) : null}

            {activeTab === "ubicacion" ? (
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField label="Parroquia">
                    <select className={formInputClass} value={form.id_parroquia} onChange={(event) => updateField("id_parroquia", event.target.value)}>
                      <option value="">Sin parroquia</option>
                      {catalogos.parroquias.map((item) => <option key={item.id} value={item.id}>{item.nombre}</option>)}
                    </select>
                  </FormField>
                  <FormField label="Plataforma">
                    <select className={formInputClass} value={form.id_plataforma} onChange={(event) => updateField("id_plataforma", event.target.value)}>
                      <option value="">Sin plataforma</option>
                      {plataformaOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                    </select>
                  </FormField>
                </div>
                <FormField label="Dirección">
                  <input className={formInputClass} required maxLength={200} value={form.direccion_texto} onChange={(event) => updateField("direccion_texto", event.target.value)} />
                </FormField>
                <FormField label="Referencia">
                  <input className={formInputClass} required maxLength={200} value={form.referencia_adicional} onChange={(event) => updateField("referencia_adicional", event.target.value)} />
                </FormField>
                <div className="grid gap-4 sm:grid-cols-2">
                  <FormField label="Latitud">
                    <input className={formInputClass} required type="number" step="0.000001" value={form.latitud} onChange={(event) => updateField("latitud", event.target.value)} />
                  </FormField>
                  <FormField label="Longitud">
                    <input className={formInputClass} required type="number" step="0.000001" value={form.longitud} onChange={(event) => updateField("longitud", event.target.value)} />
                  </FormField>
                </div>
                <LocationMap latitud={form.latitud} longitud={form.longitud} onChange={(next) => setForm((current) => ({ ...current, ...next }))} />
              </div>
            ) : null}

            {activeTab === "horarios" ? (
              <div className="space-y-4">
                <ToggleRow checked={form.abierto_24h} onChange={(value) => updateField("abierto_24h", value)}>
                  Abierto 24 horas
                </ToggleRow>
                {!form.abierto_24h ? (
                  <>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField label="Hora de inicio (por defecto)">
                        <input className={formInputClass} type="time" value={form.hora_inicio} onChange={(event) => updateField("hora_inicio", event.target.value)} />
                      </FormField>
                      <FormField label="Hora de fin (por defecto)">
                        <input className={formInputClass} type="time" value={form.hora_fin} onChange={(event) => updateField("hora_fin", event.target.value)} />
                      </FormField>
                    </div>
                    <p className="text-xs font-semibold text-app-texto-secundario">
                      El horario por defecto se aplica a los días seleccionados sin horario personalizado. Edita cada día abajo si necesitas horarios distintos.
                    </p>
                  </>
                ) : null}
                <div>
                  <p className="text-sm font-black text-app-texto-primario">Días de atención</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {days.map((day) => (
                      <ChipButton key={day.value} active={form.dias_semana.includes(day.value)} onClick={() => toggleDay(day.value)}>
                        {day.label}
                      </ChipButton>
                    ))}
                  </div>
                </div>
                {!form.abierto_24h && form.dias_semana.length > 0 && (
                  <div className="rounded-lg border border-app-primario bg-app-primario-claro p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-black text-app-primario">Horario por día</span>
                      <button
                        type="button"
                        onClick={() => setMostrarHorarioPorDia(!mostrarHorarioPorDia)}
                        className={`relative flex h-7 items-center gap-2 rounded-full px-2 text-xs font-black transition-colors ${
                          mostrarHorarioPorDia
                            ? "bg-app-primario text-white"
                            : "bg-white text-app-texto-secundario"
                        }`}
                      >
                        <span className="text-xs">{mostrarHorarioPorDia ? "Ocultar" : "Personalizar"}</span>
                        <span
                          className={`h-4 w-4 rounded-full transition-colors ${
                            mostrarHorarioPorDia ? "bg-white" : "bg-slate-300"
                          }`}
                        >
                          <span
                            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                              mostrarHorarioPorDia ? "translate-x-5" : "translate-x-0.5"
                            }`}
                          />
                        </span>
                      </button>
                    </div>
                    {mostrarHorarioPorDia && (
                      <div className="mt-3 space-y-3">
                        <p className="text-xs font-semibold text-app-texto-secundario">
                          Define uno o más horarios por día. Marca &quot;Cerrado&quot; si no abre ese día.
                        </p>
                        <div className="space-y-4">
                          {form.dias_semana.map((dayValue) => {
                            const day = days.find((item) => item.value === dayValue);
                            const schedule = form.horarios_por_dia[dayValue] || initialDaySchedule;
                            return (
                              <div
                                key={`dia-horario-${dayValue}`}
                                className="rounded-lg border border-app-borde bg-white p-3"
                              >
                                <div className="mb-2 flex items-center justify-between">
                                  <div className="flex items-center gap-3">
                                    <span className="text-sm font-black text-app-texto-primario">{day?.label}</span>
                                    <label className="flex items-center gap-1 text-xs font-semibold text-app-texto-secundario">
                                      <input
                                        type="checkbox"
                                        checked={Boolean(schedule.cerrado)}
                                        onChange={(event) => updateDaySchedule(dayValue, { cerrado: event.target.checked })}
                                        className="h-4 w-4"
                                      />
                                      Cerrado
                                    </label>
                                  </div>
                                  {!schedule.cerrado && (
                                    <button
                                      type="button"
                                      onClick={() => updateDaySchedule(dayValue, { addTurno: true })}
                                      className="text-xs font-black text-app-primario hover:underline"
                                    >
                                      + Agregar horario
                                    </button>
                                  )}
                                </div>
                                {!schedule.cerrado && schedule.turnos && schedule.turnos.length > 0 && (
                                  <div className="space-y-2">
                                    {schedule.turnos.map((turno, idx) => (
                                      <div key={`turno-${dayValue}-${idx}`} className="flex items-center gap-2">
                                        <span className="w-16 text-xs font-semibold text-app-texto-secundario">
                                          Turno {idx + 1}
                                        </span>
                                        <input
                                          className={formInputClass}
                                          type="time"
                                          value={turno.hora_inicio}
                                          onChange={(event) =>
                                            updateDaySchedule(dayValue, {
                                              updateTurno: { index: idx, data: { hora_inicio: event.target.value } },
                                            })
                                          }
                                        />
                                        <span className="text-xs text-app-texto-secundario">a</span>
                                        <input
                                          className={formInputClass}
                                          type="time"
                                          value={turno.hora_fin}
                                          onChange={(event) =>
                                            updateDaySchedule(dayValue, {
                                              updateTurno: { index: idx, data: { hora_fin: event.target.value } },
                                            })
                                          }
                                        />
                                        {schedule.turnos.length > 1 && (
                                          <button
                                            type="button"
                                            onClick={() => updateDaySchedule(dayValue, { removeTurno: idx })}
                                            className="text-xs font-black text-red-500 hover:underline"
                                          >
                                            Eliminar
                                          </button>
                                        )}
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {!schedule.cerrado && (!schedule.turnos || schedule.turnos.length === 0) && (
                                  <p className="text-xs italic text-app-texto-secundario">
                                    Sin horarios definidos.
                                  </p>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                <FormField label="Comentario (opcional)">
                  <textarea
                    className={formTextareaClass}
                    maxLength={200}
                    placeholder="Ej. Solo con reservación previa"
                    rows={3}
                    value={form.comentario_horario}
                    onChange={(event) => updateField("comentario_horario", event.target.value)}
                  />
                  <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
                    {form.comentario_horario.length}/200 caracteres
                  </p>
                </FormField>
              </div>
            ) : null}

            {activeTab === "servicios" ? (
              <div className="space-y-3">
                {[
                  ["tiene_wifi", "WiFi"],
                  ["parqueadero", "Parqueadero"],
                  ["permite_mascotas", "Mascotas"],
                  ["accesibilidad", "Accesibilidad"],
                ].map(([key, label]) => (
                  <ToggleRow key={key} checked={form[key]} onChange={(value) => updateField(key, value)}>
                    {label}
                  </ToggleRow>
                ))}
              </div>
            ) : null}

            {activeTab === "contacto" ? (
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-black text-app-texto-primario">Canales de contacto</p>
                  <p className="text-xs font-semibold text-app-texto-secundario">
                    Agrega los medios por los que los turistas pueden comunicarse con este sitio.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={addContact}
                  className="flex items-center gap-2 rounded-lg border border-dashed border-app-primario bg-app-primario-claro px-4 py-2 text-sm font-black text-app-primario hover:bg-app-primario hover:text-white"
                >
                  + Agregar contacto
                </button>

                {form.contactos.map((contact, index) => (
                  <div key={index} className="rounded-lg border border-app-borde bg-app-fondo p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="text-xs font-black uppercase text-app-texto-secundario">
                        Contacto {index + 1}
                      </span>
                      <button
                        type="button"
                        onClick={() => removeContact(index)}
                        className="text-xs font-black text-red-500 hover:underline"
                      >
                        Eliminar
                      </button>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      <FormField label="Nombre del contacto">
                        <input
                          className={formInputClass}
                          maxLength={100}
                          placeholder="Ej. Teléfono, WhatsApp, Instagram"
                          value={contact.nombre}
                          onChange={(e) => updateContact(index, "nombre", e.target.value)}
                        />
                      </FormField>
                      <FormField label="Contenido">
                        <input
                          className={formInputClass}
                          maxLength={200}
                          placeholder="Ej. 032960000, correo@ejemplo.com"
                          value={contact.contenido}
                          onChange={(e) => updateContact(index, "contenido", e.target.value)}
                        />
                      </FormField>
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            {activeTab === "imagenes" ? (
              <div className="space-y-4">
                <div className="flex gap-2">
                  <input className={formInputClass} placeholder="/api/v1/imagenes/nombre-del-atractivo/imagen.jpg" value={form.imagen_url_input} onChange={(event) => updateField("imagen_url_input", event.target.value)} />
                  <AdminActionButton variant="primary" onClick={addImageUrl}>Agregar</AdminActionButton>
                </div>
                {form.imagenes.length ? (
                  <div className="space-y-2 rounded-lg border border-app-borde bg-app-fondo p-3">
                    <p className="text-xs font-black uppercase text-app-texto-secundario">URL generadas</p>
                    {form.imagenes.map((image, index) => (
                      <input
                        key={`${image.url}-url-${index}`}
                        className={`${formInputClass} ${image.eliminada ? "line-through opacity-60" : ""}`}
                        readOnly
                        value={image.url}
                      />
                    ))}
                  </div>
                ) : null}
                <label className="flex min-h-20 cursor-pointer items-center justify-center rounded-lg border border-dashed border-app-borde bg-app-fondo px-4 text-sm font-black text-app-texto-secundario transition hover:border-app-primario hover:text-app-primario">
                  {isUploading ? "Subiendo imágenes..." : "Subir imágenes"}
                  <input className="sr-only" type="file" accept="image/*" multiple onChange={handleUpload} />
                </label>
                <div className="grid gap-3 sm:grid-cols-2">
                  {form.imagenes.map((image, index) => (
                    <div
                      key={`${image.url}-${index}`}
                      className={`rounded-lg border p-2 ${image.eliminada ? "border-red-200 bg-red-50" : "border-app-borde"}`}
                    >
                      <div className="relative">
                        <img
                          className={`h-28 w-full rounded-lg object-cover ${image.eliminada ? "opacity-45 grayscale" : ""}`}
                          src={image.url}
                          alt=""
                        />
                        {image.eliminada ? (
                          <span className="absolute left-2 top-2 rounded-full bg-red-600 px-2 py-1 text-xs font-black text-white">
                            Marcada para eliminar
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <label className="flex items-center gap-2 text-xs font-black text-app-texto-secundario">
                          <input
                            type="radio"
                            checked={!image.eliminada && image.es_principal}
                            disabled={image.eliminada}
                            onChange={() => setPrincipalImage(index)}
                          />
                          Principal
                        </label>
                        <button
                          className={`text-xs font-black ${image.eliminada ? "text-app-primario" : "text-app-error"}`}
                          type="button"
                          onClick={() => removeImage(index)}
                        >
                          {image.eliminada ? "Restaurar" : "Quitar"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {activeTab === "precios" ? (
              <div className="space-y-4">
                <ToggleRow checked={form.es_gratuito} onChange={(value) => updateField("es_gratuito", value)}>
                  Sitio gratuito
                </ToggleRow>
                {form.es_gratuito ? (
                  <p className="text-xs font-semibold text-app-texto-secundario">
                    Los sitios gratuitos no aceptan rango de precio ni tarifa de acceso.
                  </p>
                ) : (
                  <>
                    <p className="text-xs font-semibold text-app-texto-secundario">
                      Elige entre definir un rango de precio o una tarifa de acceso fija. No se pueden combinar.
                    </p>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField label="Precio mínimo">
                        <input
                          className={formInputClass}
                          disabled={Boolean(form.tarifa_acceso)}
                          type="number"
                          min="0"
                          step="0.01"
                          value={form.precio_min}
                          onChange={(event) => updateField("precio_min", event.target.value)}
                        />
                      </FormField>
                      <FormField label="Precio máximo">
                        <input
                          className={formInputClass}
                          disabled={Boolean(form.tarifa_acceso)}
                          type="number"
                          min="0"
                          step="0.01"
                          value={form.precio_max}
                          onChange={(event) => updateField("precio_max", event.target.value)}
                        />
                      </FormField>
                    </div>
                    <FormField label="Etiqueta precio">
                      <select
                        className={formInputClass}
                        disabled={Boolean(form.tarifa_acceso)}
                        value={form.etiqueta_precio}
                        onChange={(event) => updateField("etiqueta_precio", event.target.value)}
                      >
                        <option value="desconocido">Desconocido</option>
                        <option value="economico">Economico</option>
                        <option value="medio">Medio</option>
                        <option value="alto">Alto</option>
                      </select>
                    </FormField>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <FormField label="Tarifa de acceso">
                        <input
                          className={formInputClass}
                          disabled={Boolean(form.precio_min) || Boolean(form.precio_max)}
                          type="number"
                          min="0"
                          step="0.01"
                          value={form.tarifa_acceso}
                          onChange={(event) => updateField("tarifa_acceso", event.target.value)}
                        />
                      </FormField>
                      <FormField label="Condición de la tarifa">
                        <input
                          className={formInputClass}
                          disabled={!form.tarifa_acceso}
                          value={form.condicion_tarifa}
                          onChange={(event) => updateField("condicion_tarifa", event.target.value)}
                        />
                      </FormField>
                    </div>
                  </>
                )}
              </div>
            ) : null}
          </div>

          <MobilePreview form={form} categoryName={selectedCategoryName} />
        </div>

        <div className="flex justify-end gap-3 border-t border-app-borde bg-app-fondo px-5 py-4">
          <AdminActionButton onClick={onClose}>
            Cancelar
          </AdminActionButton>
          <AdminActionButton variant="primary" type="submit" disabled={isSaving || isUploading}>
            {isSaving ? "Guardando..." : isEdit ? "Actualizar atractivo" : "Guardar atractivo"}
          </AdminActionButton>
        </div>
      </form>
    </div>
  );
}

export default function AttractionsPage() {
  const sesion = obtenerSesion();
  const puedeCrear = tieneAccion(sesion, "attractions", "crear");
  const puedeEliminar = tieneAccion(sesion, "attractions", "eliminar");
  const puedeActualizar = tieneAccion(sesion, "attractions", "actualizar");
  const sinSitios = sinSitiosAsignados(sesion);
  const [catalogos, setCatalogos] = useState({ categorias: [], subcategorias: [], parroquias: [], plataformas: [] });
  const [data, setData] = useState({ items: [], total: 0, page: 1, page_size: 10 });
  const [filters, setFilters] = useState({
    q: "",
    id_categoria: "",
    id_subcategoria: "",
    estado: "all",
    servicio: "all",
    precio: "all",
    page: 1,
    page_size: 10,
  });
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingSite, setEditingSite] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  useEffect(() => {
    let isActive = true;
    obtenerCatalogosAtractivos()
      .then((response) => {
        if (isActive) setCatalogos(response);
      })
      .catch((err) => {
        if (isActive) setError(getApiErrorMessage(err, "No se pudieron cargar los atractivos"));
      });
    return () => {
      isActive = false;
    };
  }, [refreshToken]);

  useEffect(() => {
    let isActive = true;
    const timer = window.setTimeout(async () => {
      setIsLoading(true);
      setError("");
      try {
        const response = await obtenerAtractivos(filters);
        if (isActive) setData(response);
      } catch (err) {
        if (isActive) setError(getApiErrorMessage(err, "No se pudieron cargar los atractivos"));
      } finally {
        if (isActive) setIsLoading(false);
      }
    }, 250);
    return () => {
      isActive = false;
      window.clearTimeout(timer);
    };
  }, [filters, refreshToken]);

  const categoriaOptions = useMemo(
    () => [
      { value: "", label: "Categoría" },
      ...catalogos.categorias.map((categoria) => ({ value: String(categoria.id_categoria), label: categoria.nombre })),
    ],
    [catalogos.categorias],
  );

  const subcategoriaOptions = useMemo(() => {
    const filtered = filters.id_categoria
      ? catalogos.subcategorias.filter((subcategoria) => String(subcategoria.id_categoria) === filters.id_categoria)
      : catalogos.subcategorias;
    return [
      { value: "", label: "Subcategoría" },
      ...filtered.map((subcategoria) => ({ value: String(subcategoria.id_subcategoria), label: subcategoria.nombre })),
    ];
  }, [catalogos.subcategorias, filters.id_categoria]);

  function updateFilter(key, value) {
    setFilters((current) => ({
      ...current,
      [key]: value,
      page: 1,
      ...(key === "id_categoria" ? { id_subcategoria: "" } : {}),
    }));
  }

  function handleSaved() {
    setShowCreateModal(false);
    setEditingSite(null);
    setRefreshToken((current) => current + 1);
    setFilters((current) => ({ ...current, page: 1 }));
  }

  async function handleEdit(site) {
    setIsLoadingDetail(true);
    setError("");
    try {
      const detail = await obtenerDetalleAtractivo(site.id_sitio);
      setEditingSite(detail);
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudieron cargar los atractivos"));
    } finally {
      setIsLoadingDetail(false);
    }
  }

  function requestDelete(site) {
    setConfirmAction({
      title: "Eliminar atractivo",
      message: `Se eliminará el atractivo ${site.nombre} y sus imágenes asociadas.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarAtractivo(site.id_sitio),
    });
  }

  function requestToggleStatus(site) {
    const nextActive = !site.activo;
    setConfirmAction({
      title: nextActive ? "Activar atractivo" : "Desactivar atractivo",
      message: `¿${nextActive ? "Activar" : "Desactivar"} el atractivo ${site.nombre}?`,
      confirmLabel: nextActive ? "Activar" : "Desactivar",
      run: async () => cambiarEstadoAtractivo(site.id_sitio, nextActive),
    });
  }

  async function executeConfirmAction() {
    if (!confirmAction) return;
    setIsConfirming(true);
    setError("");
    try {
      await confirmAction.run();
      setConfirmAction(null);
      handleSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudieron cargar los atractivos"));
    } finally {
      setIsConfirming(false);
    }
  }

  return (
    <div className="space-y-6">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>

      <Panel className="overflow-hidden">
        <div className="grid min-w-0 gap-3 border-b border-app-borde p-4 xl:grid-cols-[minmax(220px,1fr)_auto]">
          <SearchBox
            label="Buscar atractivo"
            placeholder="Buscar atractivo..."
            value={filters.q}
            onChange={(value) => updateFilter("q", value)}
          />

          <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:flex xl:flex-wrap xl:items-center xl:justify-end">
            <SelectFilter icon label="Categoría" options={categoriaOptions} value={filters.id_categoria} onChange={(value) => updateFilter("id_categoria", value)} />
            <SelectFilter icon label="Subcategoría" options={subcategoriaOptions} value={filters.id_subcategoria} onChange={(value) => updateFilter("id_subcategoria", value)} />
            <SelectFilter icon label="Estado" options={estadoOptions} value={filters.estado} onChange={(value) => updateFilter("estado", value)} />
            <SelectFilter icon label="Servicios" options={servicioOptions} value={filters.servicio} onChange={(value) => updateFilter("servicio", value)} />
            <SelectFilter icon label="Precio" options={precioOptions} value={filters.precio} onChange={(value) => updateFilter("precio", value)} />
            {puedeCrear ? (
              <AdminActionButton icon={<PlusIcon />} variant="primary" onClick={() => setShowCreateModal(true)}>Nuevo atractivo</AdminActionButton>
            ) : null}
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-left text-sm">
            <thead className="bg-app-fondo text-xs font-black uppercase text-app-texto-secundario">
              <tr>
                <th className="min-w-[420px] px-4 py-3">Atractivo</th>
                <th className="min-w-[180px] px-4 py-3">Categoría</th>
                <th className="min-w-[180px] px-4 py-3">Subcategoría</th>
                <th className="min-w-[130px] px-4 py-3">Estado</th>
                <th className="px-4 py-3 text-right">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-app-borde">
              {isLoading ? (
                <tr><td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={5}>Cargando atractivos...</td></tr>
              ) : data.items.length ? (
                data.items.map((site) => (
                  <tr key={site.id_sitio} className="align-middle transition hover:bg-app-fondo/55">
                    <td className="px-4 py-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <img className="h-12 w-12 shrink-0 rounded-lg border border-app-borde bg-app-primario-claro object-cover" src={site.imagen_url || logoSrc} alt="" />
                        <div className="min-w-0">
                          <p className="truncate font-black text-app-texto-primario">{site.nombre}</p>
                          <p className="mt-1 max-w-xl truncate text-xs font-semibold text-app-texto-secundario">{site.descripcion_corta || "Sin descripción"}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 font-semibold text-app-texto-secundario">{site.categoria}</td>
                    <td className="px-4 py-3 font-semibold text-app-texto-secundario">{site.subcategoria || "Sin subcategoría"}</td>
                    <td className="px-4 py-3">
                      {puedeActualizar ? (
                        <button type="button" onClick={() => requestToggleStatus(site)}>
                          <StatusBadge active={site.activo} />
                        </button>
                      ) : (
                        <StatusBadge active={site.activo} />
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {puedeActualizar ? (
                          <TableActionButton icon={<EditIcon />} disabled={isLoadingDetail} onClick={() => handleEdit(site)}>
                            Editar
                          </TableActionButton>
                        ) : null}
                        {puedeEliminar ? (
                          <TableActionButton icon={<TrashIcon />} variant="danger" onClick={() => requestDelete(site)}>
                            Eliminar
                          </TableActionButton>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr><td className="px-4 py-10 text-center font-semibold text-app-texto-secundario" colSpan={5}>{sinSitios ? "No tienes atractivos asignados todavía." : "No hay atractivos con los filtros seleccionados."}</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={(page) => setFilters((current) => ({ ...current, page }))} />
      </Panel>

      {showCreateModal ? (
        <AttractionFormModal catalogos={catalogos} onClose={() => setShowCreateModal(false)} onSaved={handleSaved} setGlobalError={setError} />
      ) : null}
      {editingSite ? (
        <AttractionFormModal catalogos={catalogos} site={editingSite} onClose={() => setEditingSite(null)} onSaved={handleSaved} setGlobalError={setError} />
      ) : null}
      {confirmAction ? (
        <ConfirmDialog
          confirmLabel={confirmAction.confirmLabel}
          isLoading={isConfirming}
          message={confirmAction.message}
          onCancel={() => setConfirmAction(null)}
          onConfirm={executeConfirmAction}
          title={confirmAction.title}
        />
      ) : null}
    </div>
  );
}
