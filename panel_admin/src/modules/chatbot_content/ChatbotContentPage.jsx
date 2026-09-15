import { useEffect, useMemo, useRef, useState } from "react";
import ReactQuill from "react-quill";
import TurndownService from "turndown";
import { marked } from "marked";
import "react-quill/dist/quill.snow.css";
import AdminModal from "../../core/ui/AdminModal";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import {
  AdminActionButton,
  ChipButton,
  FormField,
  SelectFilter,
  TimedAlert,
  formTextareaClass,
} from "../../core/ui/AdminControls";
import Panel from "../../core/ui/Panel";
import PanelToolbar from "../../core/ui/PanelToolbar";
import Pagination from "../../core/ui/Pagination";
import WorkspaceShell from "../../core/ui/WorkspaceShell";
import { PlusIcon } from "../../core/ui/icons";
import EntityStatusBadge from "../../core/ui/EntityStatusBadge";
import RepositoryCard from "../../core/ui/RepositoryCard";
import SearchBox from "../../core/ui/SearchBox";
import {
  actualizarDocumentoContenido,
  agregarContenidoDocumento,
  buscarEntidadesContenido,
  crearDocumentoContenido,
  crearRepositorioContenido,
  eliminarDocumentoContenido,
  eliminarRepositorioContenido,
  obtenerContenidoDocumento,
  obtenerRepositoriosContenido,
  renombrarRepositorioContenido,
} from "./chatbotContentService";
import { getApiErrorMessage } from "../../core/api/errors";
import { obtenerSesion, tieneAccion, tieneAlcanceSitio } from "../../core/auth/authStorage";

const quillModules = {
  toolbar: [
    [{ header: [1, 2, 3, false] }],
    ["bold", "italic", "underline"],
    [{ list: "ordered" }, { list: "bullet" }],
    ["blockquote", "link"],
    ["clean"],
  ],
  history: {
    delay: 500,
    maxStack: 100,
    userOnly: true,
  },
};

const turndownService = new TurndownService({
  bulletListMarker: "-",
  codeBlockStyle: "fenced",
  headingStyle: "atx",
});

const markdownSectionRegex = /^(#{1,3})\s+(.+?)\s*$/;
const hashWrappedSectionRegex = /^#{1,6}\s*(.+?)\s*#{1,6}$/;
const boldSectionRegex = /^\*\*(.+?)\*\*$/;
const PAGE_SIZE = 6;

function getSectionTitleFromLine(line) {
  const text = line.trim();
  const markdownMatch = text.match(markdownSectionRegex);
  if (markdownMatch) return markdownMatch[2]?.trim();
  const hashWrappedMatch = text.match(hashWrappedSectionRegex);
  if (hashWrappedMatch) return hashWrappedMatch[1]?.replace(/#/g, "").trim();
  const boldMatch = text.match(boldSectionRegex);
  if (boldMatch) return boldMatch[1]?.trim();
  return "";
}

function getMarkdownSections(markdown) {
  const content = markdown.trim();
  const sections = [];
  let current = null;

  content.split(/\r?\n/).forEach((line) => {
    const title = getSectionTitleFromLine(line);
    if (title) {
      if (current?.content.join("\n").trim()) {
        sections.push({ title: current.title, content: current.content.join("\n").trim() });
      }
      current = { title, content: [] };
      return;
    }
    if (current) {
      current.content.push(line);
    }
  });

  if (current?.content.join("\n").trim()) {
    sections.push({ title: current.title, content: current.content.join("\n").trim() });
  }

  return sections;
}

function RepositoryModal({ onClose, onSaved }) {
  const [filters, setFilters] = useState({ q: "", tipo: "all" });
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  async function handleSearch(nextFilters = filters) {
    setIsSearching(true);
    setError("");
    try {
      const response = await buscarEntidadesContenido({ ...nextFilters, limit: 30 });
      setResults(response);
      if (!response.some((item) => selected && item.origen === selected.origen && item.id_vinculo === selected.id_vinculo)) {
        setSelected(null);
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsSearching(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      handleSearch(filters);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [filters.q, filters.tipo]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!selected) {
      setError("Selecciona un sitio o ruta");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await crearRepositorioContenido({
        origen: selected.origen,
        id_vinculo: selected.id_vinculo,
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AdminModal
      error={error}
      isSaving={isSaving}
      maxWidth="max-w-3xl"
      onClose={onClose}
      onDismissError={() => setError("")}
      onSubmit={handleSubmit}
      submitLabel="Crear repositorio"
      title="Crear repositorio"
      subtitle="Elige el sitio o la ruta."
    >
      <div className="grid gap-3">
        <SearchBox
          label="Buscar sitio o ruta"
          placeholder="Buscar por nombre o descripción..."
          value={filters.q}
          onChange={(q) => setFilters((current) => ({ ...current, q }))}
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <ChipButton active={filters.tipo === "all"} onClick={() => setFilters((current) => ({ ...current, tipo: "all" }))}>
          Todos
        </ChipButton>
        <ChipButton active={filters.tipo === "sitio"} onClick={() => setFilters((current) => ({ ...current, tipo: "sitio" }))}>
          Sitios
        </ChipButton>
        <ChipButton active={filters.tipo === "ruta"} onClick={() => setFilters((current) => ({ ...current, tipo: "ruta" }))}>
          Rutas
        </ChipButton>
      </div>

      <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
        {results.length ? (
          results.map((item) => {
            const isSelected =
              selected?.origen === item.origen &&
              selected?.id_vinculo === item.id_vinculo;
            return (
              <button
                key={`${item.origen}-${item.id_vinculo}`}
                className={`w-full rounded-lg border px-4 py-3 text-left transition ${
                  isSelected
                    ? "border-app-primario bg-app-primario-claro shadow-[0_0_0_2px_rgba(0,135,111,0.12)]"
                    : "border-app-borde bg-app-tarjeta hover:border-app-primario"
                }`}
                type="button"
                onClick={() => setSelected(item)}
              >
                <span className="flex flex-wrap items-center justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block font-black text-app-texto-primario">{item.nombre}</span>
                    <span className="mt-1 block line-clamp-2 text-sm font-semibold text-app-texto-secundario">
                      {item.descripcion || "Sin descripción"}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <EntityStatusBadge active>{item.origen === "ruta" ? "Ruta" : "Sitio"}</EntityStatusBadge>
                    <EntityStatusBadge active={item.activo} />
                  </span>
                </span>
              </button>
            );
          })
        ) : (
          <div className="rounded-lg border border-dashed border-app-borde bg-app-fondo px-4 py-8 text-center text-sm font-semibold text-app-texto-secundario">
            {isSearching ? "Buscando sitios y rutas..." : "No hay sitios o rutas para mostrar."}
          </div>
        )}
      </div>
    </AdminModal>
  );
}

function tituloCortoDesdeTexto(text) {
  const normalized = text.trim();
  if (!normalized) return "";
  const firstSentence = normalized.split(/[.!?]/)[0]?.trim();
  if (firstSentence && firstSentence.length <= 200) {
    return firstSentence;
  }
  return normalized.slice(0, 120).trim();
}

function tituloInicialDocumento(document, repository) {
  const titulo = (document?.titulo || "").trim();
  const descripcion = (document?.descripcion || "").trim();
  const nombreRepositorio = repository?.nombre?.trim() || "";

  if (!titulo) {
    return nombreRepositorio || tituloCortoDesdeTexto(descripcion);
  }
  if (!descripcion || titulo === descripcion) {
    return nombreRepositorio || tituloCortoDesdeTexto(descripcion);
  }
  if (titulo.length > 120 && descripcion.startsWith(titulo.slice(0, 80))) {
    return nombreRepositorio || tituloCortoDesdeTexto(descripcion);
  }
  return titulo;
}

function documentoRecienCreado(repositoryResponse, titulo, descripcion) {
  const documentos = repositoryResponse?.documentos || [];
  const tituloNormalizado = titulo.trim();
  const descripcionNormalizada = descripcion.trim();
  return (
    documentos.find(
      (item) =>
        item.titulo === tituloNormalizado && item.descripcion === descripcionNormalizada,
    ) ||
    [...documentos].sort((left, right) => right.id_documento - left.id_documento)[0] ||
    null
  );
}

function DocumentModal({ document, mode = "create", onClose, onSaved, repository }) {
  const [form, setForm] = useState(() => ({
    titulo: tituloInicialDocumento(document, repository),
    descripcion: document?.descripcion || "",
  }));
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const isEdit = mode === "edit";

  useEffect(() => {
    setForm({
      titulo: tituloInicialDocumento(document, repository),
      descripcion: document?.descripcion || "",
    });
    setError("");
  }, [document, repository, mode]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.titulo.trim()) {
      setError("Ingresa el título del documento");
      return;
    }
    if (!form.descripcion.trim()) {
      setError("Ingresa la descripción del documento");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const payload = {
        titulo: form.titulo.trim(),
        descripcion: form.descripcion.trim(),
      };
      if (isEdit) {
        await actualizarDocumentoContenido(document.id_documento, payload);
        onSaved({ mode: "edit" });
      } else {
        const repositoryResponse = await crearDocumentoContenido(repository.slug, payload);
        const savedDocument = documentoRecienCreado(
          repositoryResponse,
          payload.titulo,
          payload.descripcion,
        );
        if (!savedDocument) {
          setError("No se encontró el documento creado");
          return;
        }
        onSaved({ mode: "create", repository, document: savedDocument });
      }
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AdminModal
      error={error}
      isSaving={isSaving}
      onClose={onClose}
      onDismissError={() => setError("")}
      onSubmit={handleSubmit}
      submitLabel={isEdit ? "Guardar cambios" : "Crear documento"}
      title={isEdit ? "Editar datos del documento" : "Crear documento"}
      subtitle={isEdit ? `${repository.nombre} · título y descripción` : repository.nombre}
    >
      <FormField label="Título">
        <input
          className="h-11 w-full rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-semibold text-app-texto-primario outline-none transition focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
          maxLength={500}
          required
          value={form.titulo}
          onChange={(event) => {
            setError("");
            setForm((current) => ({ ...current, titulo: event.target.value }));
          }}
        />
      </FormField>
      <FormField label="Descripción">
        <textarea
          className={formTextareaClass}
          maxLength={4000}
          rows={5}
          required
          value={form.descripcion}
          onChange={(event) => {
            setError("");
            setForm((current) => ({ ...current, descripcion: event.target.value }));
          }}
        />
      </FormField>
    </AdminModal>
  );
}

function RepositoryRenameModal({ onClose, onSaved, repository }) {
  const [form, setForm] = useState({ nombre: repository.nombre || "" });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.nombre.trim()) {
      setError("Ingresa el nombre del repositorio");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await renombrarRepositorioContenido(repository.slug, {
        nombre: form.nombre.trim(),
      });
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <AdminModal
      error={error}
      isSaving={isSaving}
      onClose={onClose}
      onDismissError={() => setError("")}
      onSubmit={handleSubmit}
      submitLabel="Guardar repositorio"
      title="Renombrar repositorio"
      subtitle="El sitio o ruta original no cambia."
    >
      <FormField label="Nombre del repositorio">
        <input
          className="h-11 w-full rounded-lg border border-app-borde bg-app-tarjeta px-3 text-sm font-semibold text-app-texto-primario outline-none transition focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
          maxLength={180}
          required
          value={form.nombre}
          onChange={(event) => {
            setError("");
            setForm({ nombre: event.target.value });
          }}
        />
      </FormField>
    </AdminModal>
  );
}

function ContentEditorPage({ document, onBack, onSaved, repository }) {
  const [html, setHtml] = useState("");
  const [markdown, setMarkdown] = useState("");
  const savedMarkdownRef = useRef("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [pendingLeave, setPendingLeave] = useState(false);

  const sections = useMemo(() => getMarkdownSections(markdown), [markdown]);

  useEffect(() => {
    let isActive = true;
    async function loadContent() {
      setIsLoading(true);
      setError("");
      try {
        const response = await obtenerContenidoDocumento(document.id_documento);
        const nextMarkdown = response.contenido || "";
        const nextHtml = nextMarkdown ? marked.parse(nextMarkdown) : "";
        if (isActive) {
          savedMarkdownRef.current = nextMarkdown.trim();
          setMarkdown(nextMarkdown);
          setHtml(nextHtml);
        }
      } catch (err) {
        if (isActive) {
          setError(getApiErrorMessage(err, "No se pudo completar la operación"));
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    loadContent();
    return () => {
      isActive = false;
    };
  }, [document.id_documento]);

  function handleEditorChange(value) {
    setHtml(value);
    setMarkdown(turndownService.turndown(value));
  }

  function hasUnsavedChanges() {
    return markdown.trim() !== savedMarkdownRef.current;
  }

  function handleBack() {
    if (!hasUnsavedChanges()) {
      onBack();
      return;
    }
    setPendingLeave(true);
  }

  useEffect(() => {
    function handleBeforeUnload(event) {
      if (!hasUnsavedChanges()) return;
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [markdown]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!markdown.trim()) {
      setError("Ingresa el contenido del documento");
      return;
    }
    if (!sections.length) {
      setError("Agrega al menos una sección con título y texto.");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await agregarContenidoDocumento(document.id_documento, {
        contenido: markdown.trim(),
      });
      savedMarkdownRef.current = markdown.trim();
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <>
      <form className="h-full" onSubmit={handleSubmit}>
        <WorkspaceShell
          actions={(
            <>
              <AdminActionButton onClick={handleBack}>Cancelar</AdminActionButton>
              <AdminActionButton variant="primary" type="submit" disabled={isSaving || isLoading}>
                {isSaving ? (
                  <span className="inline-flex items-center gap-2">
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
                    Guardando...
                  </span>
                ) : (
                  "Guardar contenido"
                )}
              </AdminActionButton>
            </>
          )}
          onBack={handleBack}
          subtitle={`${repository.nombre} · ${sections.length} secciones · usa títulos para separar bloques`}
          title={document.titulo}
        >
        <TimedAlert className="mx-4 mt-4 shrink-0" onDismiss={() => setError("")}>{error}</TimedAlert>

        <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
          <section className="flex min-h-0 flex-1 flex-col border-b border-app-borde lg:max-w-[50%] lg:border-b-0 lg:border-r">
            <div className="shrink-0 border-b border-app-borde px-4 py-3 text-xs font-black uppercase text-app-texto-secundario">
              Editor
            </div>
            <div className="flex min-h-0 flex-1 flex-col bg-white">
              {isLoading ? (
                <div className="grid flex-1 place-items-center text-sm font-semibold text-app-texto-secundario">
                  Cargando contenido...
                </div>
              ) : (
                <ReactQuill
                  className="content-quill content-quill--workspace"
                  modules={quillModules}
                  placeholder="Escribe un título y el contenido debajo."
                  theme="snow"
                  value={html}
                  onChange={handleEditorChange}
                />
              )}
            </div>
          </section>

          <section className="flex min-h-0 flex-1 flex-col">
            <div className="shrink-0 border-b border-app-borde px-4 py-3 text-xs font-black uppercase text-app-texto-secundario">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <span>Vista previa</span>
                <span className={`rounded-full px-2 py-1 ${sections.length ? "bg-emerald-50 text-app-primario" : "bg-red-50 text-app-error"}`}>
                  {sections.length} secciones
                </span>
              </div>
            </div>
            <div className="shrink-0 border-b border-app-borde bg-app-fondo px-4 py-3">
              {sections.length ? (
                <div className="flex flex-wrap gap-2">
                  {sections.map((section, index) => (
                    <span
                      key={`${section.title}-${index}`}
                      className="inline-flex max-w-full items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-black text-app-primario"
                    >
                      <span className="grid h-5 min-w-5 place-items-center rounded-full bg-app-primario text-[10px] text-white">
                        {index + 1}
                      </span>
                      <span className="truncate">{section.title}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <p className="text-sm font-semibold text-app-error">
                  No hay secciones. Escribe un título y agrega texto debajo.
                </p>
              )}
            </div>
            <div
              className="prose-preview prose-preview--workspace bg-app-tarjeta p-5 text-sm leading-7 text-app-texto-primario"
              dangerouslySetInnerHTML={{ __html: html || "<p></p>" }}
            />
          </section>
        </div>
        </WorkspaceShell>
      </form>
      {pendingLeave ? (
        <ConfirmDialog
          confirmLabel="Salir sin guardar"
          message="Hay cambios de contenido sin guardar. Si sales ahora, se perderán."
          onCancel={() => setPendingLeave(false)}
          onConfirm={onBack}
          title="Cambios sin guardar"
        />
      ) : null}
    </>
  );
}

export default function ChatbotContentPage() {
  const sesion = obtenerSesion();
  const puedeCrear = tieneAccion(sesion, "chatbot_content", "crear");
  const puedeEliminar = tieneAccion(sesion, "chatbot_content", "eliminar");
  const puedeActualizar = tieneAccion(sesion, "chatbot_content", "actualizar");
  const tieneAlcance = tieneAlcanceSitio(sesion);
  // Los dueños gestionan documentos del repositorio creado para su sitio;
  // la gestión del repositorio queda reservada a usuarios globales.
  const puedeCrearDocumento = puedeCrear || tieneAlcance;
  const puedeActualizarDocumento = puedeActualizar || tieneAlcance;
  const puedeEliminarDocumento = puedeEliminar || tieneAlcance;
  const puedeGestionarRepositorios = !tieneAlcance;
  const [repositories, setRepositories] = useState([]);
  const [expandedSlugs, setExpandedSlugs] = useState(new Set());
  const [filters, setFilters] = useState({ q: "", tipo: "all", estado: "all" });
  const [page, setPage] = useState(1);
  const [editorContext, setEditorContext] = useState(null);
  const [modal, setModal] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isConfirming, setIsConfirming] = useState(false);

  async function loadRepositories() {
    setIsLoading(true);
    setError("");
    try {
      const response = await obtenerRepositoriosContenido();
      setRepositories(response);
      setPage((current) => Math.min(current, Math.max(Math.ceil(response.length / PAGE_SIZE), 1)));
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadRepositories();
  }, []);

  const totals = useMemo(
    () => ({
      repositorios: repositories.length,
      documentos: repositories.reduce((total, item) => total + item.total_documentos, 0),
    }),
    [repositories],
  );

  const filteredRepositories = useMemo(() => {
    const q = filters.q.trim().toLowerCase();
    return repositories
      .filter((repository) => filters.tipo === "all" || repository.origen === filters.tipo)
      .map((repository) => {
        const documents = repository.documentos.filter((document) => {
          const matchesText =
            !q ||
            repository.nombre.toLowerCase().includes(q) ||
            document.titulo.toLowerCase().includes(q) ||
            document.descripcion.toLowerCase().includes(q) ||
            String(document.ruta_archivo || "").toLowerCase().includes(q);
          const matchesState =
            filters.estado === "all" ||
            (filters.estado === "activo" && document.activo) ||
            (filters.estado === "inactivo" && !document.activo);
          return matchesText && matchesState;
        });

        const repositoryMatches = !q || repository.nombre.toLowerCase().includes(q);
        if (!documents.length && !repositoryMatches) {
          return null;
        }
        return { ...repository, documentosFiltrados: documents };
      })
      .filter(Boolean);
  }, [filters, repositories]);

  useEffect(() => {
    setPage(1);
  }, [filters.q, filters.tipo, filters.estado]);

  useEffect(() => {
    const hasActiveFilter =
      filters.q.trim() ||
      filters.tipo !== "all" ||
      filters.estado !== "all";

    if (!hasActiveFilter) {
      setExpandedSlugs(new Set());
      return;
    }

    setExpandedSlugs(new Set(filteredRepositories.map((repository) => repository.slug)));
  }, [filters.q, filters.tipo, filters.estado, filteredRepositories]);

  const paginatedRepositories = useMemo(
    () => filteredRepositories.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filteredRepositories, page],
  );

  function toggleRepository(slug) {
    setExpandedSlugs((current) => {
      const next = new Set(current);
      if (next.has(slug)) {
        next.delete(slug);
      } else {
        next.add(slug);
      }
      return next;
    });
  }

  function handleSaved() {
    setModal(null);
    setEditorContext(null);
    loadRepositories();
  }

  function handleDocumentSaved(result) {
    setModal(null);
    if (result?.mode === "create" && result.repository && result.document) {
      setEditorContext({ repository: result.repository, document: result.document });
    }
    loadRepositories();
  }

  function requestDeleteDocument(document) {
    setConfirmAction({
      title: "Eliminar documento",
      message: `Se eliminará el documento ${document.titulo}.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarDocumentoContenido(document.id_documento),
    });
  }

  function requestDeleteRepository(repository) {
    setConfirmAction({
      title: "Eliminar repositorio",
      message: `Se eliminará el repositorio ${repository.nombre} y todos sus documentos.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarRepositorioContenido(repository.slug),
    });
  }

  async function executeConfirmAction() {
    if (!confirmAction) return;
    setIsConfirming(true);
    setError("");
    try {
      await confirmAction.run();
      setConfirmAction(null);
      await loadRepositories();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsConfirming(false);
    }
  }

  if (editorContext) {
    return (
      <ContentEditorPage
        document={editorContext.document}
        repository={editorContext.repository}
        onBack={() => setEditorContext(null)}
        onSaved={handleSaved}
      />
    );
  }

  return (
    <div className="space-y-5">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>

      <Panel className="overflow-hidden">
        <PanelToolbar
          search={
            <SearchBox
              label="Buscar documento"
              placeholder="Buscar repositorio o documento..."
              value={filters.q}
              onChange={(q) => setFilters((current) => ({ ...current, q }))}
            />
          }
          filters={
            <>
              <SelectFilter
                icon
                label="Estado"
                options={[
                  { value: "all", label: "Estado" },
                  { value: "activo", label: "Activo" },
                  { value: "inactivo", label: "Inactivo" },
                ]}
                value={filters.estado}
                onChange={(estado) => setFilters((current) => ({ ...current, estado }))}
              />
              <SelectFilter
                icon
                label="Tipo"
                options={[
                  { value: "all", label: "Rutas y sitios" },
                  { value: "sitio", label: "Sitios" },
                  { value: "ruta", label: "Rutas" },
                ]}
                value={filters.tipo}
                onChange={(tipo) => setFilters((current) => ({ ...current, tipo }))}
              />
            </>
          }
          actions={
            puedeCrear && puedeGestionarRepositorios ? (
              <AdminActionButton
                icon={<PlusIcon />}
                variant="primary"
                onClick={() => setModal({ type: "repository-create" })}
              >
                Crear repositorio
              </AdminActionButton>
            ) : null
          }
          meta={`${totals.repositorios} repositorios · ${totals.documentos} documentos`}
        />
      </Panel>

      {isLoading ? (
        <Panel className="p-8 text-center text-sm font-semibold text-app-texto-secundario">
          Cargando repositorios...
        </Panel>
      ) : filteredRepositories.length ? (
        <div>
          <div className="space-y-3">
            {paginatedRepositories.map((repository) => (
              <RepositoryCard
                key={repository.slug}
                documents={repository.documentosFiltrados}
                expanded={expandedSlugs.has(repository.slug)}
                repository={repository}
                onAddContent={puedeActualizarDocumento ? (document) => setEditorContext({ document, repository }) : undefined}
                onCreateDocument={puedeCrearDocumento ? () => setModal({ type: "document-create", repository }) : undefined}
                onDeleteDocument={puedeEliminarDocumento ? requestDeleteDocument : undefined}
                onDeleteRepository={puedeEliminar && puedeGestionarRepositorios ? () => requestDeleteRepository(repository) : undefined}
                onEditDocument={puedeActualizarDocumento ? (document) => setModal({ type: "document-edit", repository, document }) : undefined}
                onRenameRepository={puedeActualizar && puedeGestionarRepositorios ? () => setModal({ type: "repository-rename", repository }) : undefined}
                onToggle={() => toggleRepository(repository.slug)}
              />
            ))}
          </div>
          {filteredRepositories.length > PAGE_SIZE ? (
            <Panel className="mt-3 overflow-hidden">
              <Pagination
                page={page}
                pageSize={PAGE_SIZE}
                total={filteredRepositories.length}
                onPageChange={setPage}
              />
            </Panel>
          ) : null}
        </div>
      ) : (
        <Panel className="p-8 text-center">
          <p className="text-sm font-semibold text-app-texto-secundario">
            No hay repositorios de contenido creados.
          </p>
          {puedeCrear && puedeGestionarRepositorios ? (
            <div className="mt-4">
              <AdminActionButton
                icon={<PlusIcon />}
                variant="primary"
                onClick={() => setModal({ type: "repository-create" })}
              >
                Crear repositorio
              </AdminActionButton>
            </div>
          ) : null}
        </Panel>
      )}

      {modal?.type === "repository-create" ? (
        <RepositoryModal onClose={() => setModal(null)} onSaved={handleSaved} />
      ) : null}

      {modal?.type === "document-create" ? (
        <DocumentModal
          repository={modal.repository}
          onClose={() => setModal(null)}
          onSaved={handleDocumentSaved}
        />
      ) : null}

      {modal?.type === "repository-rename" ? (
        <RepositoryRenameModal
          repository={modal.repository}
          onClose={() => setModal(null)}
          onSaved={handleSaved}
        />
      ) : null}

      {modal?.type === "document-edit" ? (
        <DocumentModal
          mode="edit"
          document={modal.document}
          repository={modal.repository}
          onClose={() => setModal(null)}
          onSaved={handleDocumentSaved}
        />
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
