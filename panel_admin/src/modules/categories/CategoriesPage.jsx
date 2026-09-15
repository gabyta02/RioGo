import { useEffect, useMemo, useState } from "react";
import AdminModal from "../../core/ui/AdminModal";
import ConfirmDialog from "../../core/ui/ConfirmDialog";
import {
  AdminActionButton,
  FormField,
  TableActionButton,
  TimedAlert,
  ToggleRow,
  formInputClass,
} from "../../core/ui/AdminControls";
import EntityStatusBadge from "../../core/ui/EntityStatusBadge";
import EntityIcon from "../../core/ui/EntityIcon";
import ExpandToggleButton from "../../core/ui/ExpandToggleButton";
import Panel from "../../core/ui/Panel";
import PanelToolbar from "../../core/ui/PanelToolbar";
import Pagination from "../../core/ui/Pagination";
import SearchBox from "../../core/ui/SearchBox";
import { CategoryIcon, EditIcon, PlusIcon, TrashIcon } from "../../core/ui/icons";
import { layout, text } from "../../core/typography";
import { obtenerSesion, tieneAccion } from "../../core/auth/authStorage";
import {
  actualizarCategoria,
  actualizarSubcategoria,
  cambiarEstadoCategoria,
  cambiarEstadoSubcategoria,
  crearCategoria,
  crearSubcategoria,
  eliminarCategoria,
  eliminarSubcategoria,
  obtenerCategoriasDetalle,
} from "./categoriesService";
import { getApiErrorMessage } from "../../core/api/errors";

const PAGE_SIZE = 6;

function CategoryFormModal({
  category,
  mode,
  onClose,
  onSaved,
}) {
  const [form, setForm] = useState({
    nombre: category?.nombre || "",
    activo: category?.activo ?? true,
  });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const isEdit = mode === "edit";

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.nombre.trim()) {
      setError("Ingresa el nombre de la categoría");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      if (isEdit) {
        await actualizarCategoria(category.id_categoria, {
          nombre: form.nombre.trim(),
          activo: form.activo,
        });
      } else {
        await crearCategoria({
          nombre: form.nombre.trim(),
          activo: form.activo,
        });
      }
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
      submitLabel={isEdit ? "Guardar categoría" : "Crear categoría"}
      title={isEdit ? "Editar categoría" : "Nueva categoría"}
    >
      <FormField label="Nombre">
        <input
          className={formInputClass}
          maxLength={100}
          required
          value={form.nombre}
          onChange={(event) => {
            setError("");
            setForm((current) => ({ ...current, nombre: event.target.value }));
          }}
        />
      </FormField>
      <ToggleRow
        checked={form.activo}
        onChange={(activo) => setForm((current) => ({ ...current, activo }))}
      >
        Categoría activa
      </ToggleRow>
    </AdminModal>
  );
}

function SubcategoryFormModal({
  categories,
  category,
  onClose,
  onSaved,
  subcategory,
}) {
  const [form, setForm] = useState({
    id_categoria: String(subcategory?.id_categoria || category?.id_categoria || ""),
    nombre: subcategory?.nombre || "",
    activo: subcategory?.activo ?? true,
  });
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const isEdit = Boolean(subcategory);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form.id_categoria) {
      setError("Selecciona una categoría");
      return;
    }
    if (!form.nombre.trim()) {
      setError("Ingresa el nombre de la subcategoría");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      const payload = {
        id_categoria: Number(form.id_categoria),
        nombre: form.nombre.trim(),
        activo: form.activo,
      };
      if (isEdit) {
        await actualizarSubcategoria(subcategory.id_subcategoria, payload);
      } else {
        await crearSubcategoria(payload);
      }
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
      submitLabel={isEdit ? "Guardar subcategoría" : "Crear subcategoría"}
      title={isEdit ? "Editar subcategoría" : "Nueva subcategoría"}
      subtitle="Elige la categoría a la que pertenece."
    >
      <FormField label="Categoría">
        <select
          className={formInputClass}
          required
          value={form.id_categoria}
          onChange={(event) => {
            setError("");
            setForm((current) => ({ ...current, id_categoria: event.target.value }));
          }}
        >
          <option value="">Seleccionar categoría</option>
          {categories.map((item) => (
            <option key={item.id_categoria} value={item.id_categoria}>
              {item.nombre}
            </option>
          ))}
        </select>
      </FormField>
      <FormField label="Nombre">
        <input
          className={formInputClass}
          maxLength={100}
          required
          value={form.nombre}
          onChange={(event) => {
            setError("");
            setForm((current) => ({ ...current, nombre: event.target.value }));
          }}
        />
      </FormField>
      <ToggleRow
        checked={form.activo}
        onChange={(activo) => setForm((current) => ({ ...current, activo }))}
      >
        Subcategoría activa
      </ToggleRow>
    </AdminModal>
  );
}

function CategoryCard({
  category,
  expanded,
  onAddSubcategory,
  onDeleteCategory,
  onDeleteSubcategory,
  onEditCategory,
  onEditSubcategory,
  onToggleCategoryStatus,
  onToggleSubcategoryStatus,
  onToggle,
  subcategorias = category.subcategorias,
}) {
  return (
    <Panel className="overflow-hidden">
      <div className={`flex flex-wrap items-center justify-between ${layout.cardGap} ${layout.cardPadding}`}>
        <button
          className={`flex min-w-0 items-center text-left ${layout.cardGap}`}
          type="button"
          onClick={onToggle}
        >
          <EntityIcon>
            <CategoryIcon />
          </EntityIcon>
          <span className="min-w-0">
            <span className={`flex flex-wrap items-center ${layout.cardGap}`}>
              <span className={text.entityTitle}>{category.nombre}</span>
              <span
                role={onToggleCategoryStatus ? "button" : undefined}
                tabIndex={onToggleCategoryStatus ? 0 : undefined}
                onClick={(event) => {
                  if (!onToggleCategoryStatus) return;
                  event.stopPropagation();
                  onToggleCategoryStatus();
                }}
                onKeyDown={(event) => {
                  if (!onToggleCategoryStatus) return;
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    event.stopPropagation();
                    onToggleCategoryStatus();
                  }
                }}
              >
                <EntityStatusBadge active={category.activo} />
              </span>
            </span>
            <span className={`mt-1 block ${text.entityMeta}`}>
              {category.total_atractivos} atractivos · {category.total_subcategorias} subcategorías
            </span>
          </span>
        </button>

        <div className={`flex flex-wrap items-center ${layout.cardGap}`}>
          {onEditCategory ? (
            <TableActionButton icon={<EditIcon />} onClick={onEditCategory}>
              Editar
            </TableActionButton>
          ) : null}
          {onDeleteCategory ? (
            <TableActionButton icon={<TrashIcon />} variant="danger" onClick={onDeleteCategory}>
              Eliminar
            </TableActionButton>
          ) : null}
          <ExpandToggleButton expanded={expanded} onClick={onToggle} />
        </div>
      </div>

      {expanded ? (
        <div className={`border-t border-app-borde bg-app-fondo/55 ${layout.cardPadding}`}>
          <div className={`mb-4 flex flex-wrap items-center justify-between ${layout.cardGap}`}>
            <p className={text.sectionLabel}>Subcategorías</p>
            {onAddSubcategory ? (
              <TableActionButton icon={<PlusIcon />} onClick={onAddSubcategory}>
                Añadir
              </TableActionButton>
            ) : null}
          </div>

          <div className="space-y-2">
            {subcategorias.length ? (
              subcategorias.map((subcategory) => (
                <div
                  key={subcategory.id_subcategoria}
                  className={`flex flex-wrap items-center justify-between rounded-lg border border-app-borde bg-app-tarjeta px-4 py-3 shadow-sm ${layout.cardGap}`}
                >
                  <div className={`flex min-w-0 items-center ${layout.cardGap}`}>
                    <span className="h-2 w-2 shrink-0 rounded-full bg-app-exito" />
                    <div>
                      <p className={text.entityTitle}>{subcategory.nombre}</p>
                      <p className={`mt-1 ${text.entityMeta}`}>
                        {subcategory.total_atractivos} atractivos
                      </p>
                    </div>
                  </div>
                  <div className={`flex flex-wrap items-center ${layout.cardGap}`}>
                    {onToggleSubcategoryStatus ? (
                      <button type="button" onClick={() => onToggleSubcategoryStatus(subcategory)}>
                        <EntityStatusBadge active={subcategory.activo} />
                      </button>
                    ) : (
                      <EntityStatusBadge active={subcategory.activo} />
                    )}
                    {onEditSubcategory ? (
                      <TableActionButton icon={<EditIcon />} onClick={() => onEditSubcategory(subcategory)}>
                        Editar
                      </TableActionButton>
                    ) : null}
                    {onDeleteSubcategory ? (
                      <TableActionButton icon={<TrashIcon />} variant="danger" onClick={() => onDeleteSubcategory(subcategory)}>
                        Eliminar
                      </TableActionButton>
                    ) : null}
                  </div>
                </div>
              ))
            ) : (
              <div className={`rounded-lg border border-dashed border-app-borde bg-app-tarjeta px-4 py-6 text-center ${text.empty}`}>
                No hay subcategorías registradas.
              </div>
            )}
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

export default function CategoriesPage() {
  const sesion = obtenerSesion();
  const puedeCrear = tieneAccion(sesion, "categories", "crear");
  const puedeActualizar = tieneAccion(sesion, "categories", "actualizar");
  const puedeEliminar = tieneAccion(sesion, "categories", "eliminar");
  const [categories, setCategories] = useState([]);
  const [expandedIds, setExpandedIds] = useState(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [modal, setModal] = useState(null);
  const [confirmAction, setConfirmAction] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isConfirming, setIsConfirming] = useState(false);

  async function loadCategories() {
    setIsLoading(true);
    setError("");
    try {
      const response = await obtenerCategoriasDetalle();
      setCategories(response);
      setPage((current) => Math.min(current, Math.max(Math.ceil(response.length / PAGE_SIZE), 1)));
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadCategories();
  }, []);

  const totals = useMemo(
    () => ({
      categorias: categories.length,
      subcategorias: categories.reduce((total, item) => total + item.subcategorias.length, 0),
    }),
    [categories],
  );

  const filteredCategories = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) {
      return categories.map((category) => ({
        ...category,
        subcategoriasVisibles: category.subcategorias,
      }));
    }

    return categories
      .map((category) => {
        const categoryMatches = category.nombre.toLowerCase().includes(query);
        const subcategoriasVisibles = category.subcategorias.filter((subcategory) =>
          subcategory.nombre.toLowerCase().includes(query),
        );

        if (!categoryMatches && !subcategoriasVisibles.length) {
          return null;
        }

        return {
          ...category,
          subcategoriasVisibles: categoryMatches ? category.subcategorias : subcategoriasVisibles,
        };
      })
      .filter(Boolean);
  }, [categories, searchQuery]);

  useEffect(() => {
    setPage(1);
  }, [searchQuery]);

  useEffect(() => {
    const query = searchQuery.trim();
    if (!query) {
      setExpandedIds(new Set());
      return;
    }

    setExpandedIds(new Set(filteredCategories.map((category) => category.id_categoria)));
  }, [searchQuery, filteredCategories]);

  const paginatedCategories = useMemo(
    () => filteredCategories.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [filteredCategories, page],
  );

  function toggleCategory(idCategoria) {
    setExpandedIds((current) => {
      const next = new Set(current);
      if (next.has(idCategoria)) {
        next.delete(idCategoria);
      } else {
        next.add(idCategoria);
      }
      return next;
    });
  }

  function requestDeleteCategory(category) {
    setConfirmAction({
      title: "Eliminar categoría",
      message: `Se eliminará la categoría ${category.nombre}, sus subcategorías y los atractivos asociados.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarCategoria(category.id_categoria),
    });
  }

  function requestDeleteSubcategory(subcategory) {
    setConfirmAction({
      title: "Eliminar subcategoría",
      message: `Se eliminará la subcategoría ${subcategory.nombre} y los atractivos asociados.`,
      confirmLabel: "Eliminar",
      run: async () => eliminarSubcategoria(subcategory.id_subcategoria),
    });
  }

  function requestToggleCategory(category) {
    const nextActive = !category.activo;
    setConfirmAction({
      title: nextActive ? "Activar categoría" : "Desactivar categoría",
      message: `¿${nextActive ? "Activar" : "Desactivar"} la categoría ${category.nombre}?`,
      confirmLabel: nextActive ? "Activar" : "Desactivar",
      run: async () => cambiarEstadoCategoria(category.id_categoria, nextActive),
    });
  }

  function requestToggleSubcategory(subcategory) {
    const nextActive = !subcategory.activo;
    setConfirmAction({
      title: nextActive ? "Activar subcategoría" : "Desactivar subcategoría",
      message: `¿${nextActive ? "Activar" : "Desactivar"} la subcategoría ${subcategory.nombre}?`,
      confirmLabel: nextActive ? "Activar" : "Desactivar",
      run: async () => cambiarEstadoSubcategoria(subcategory.id_subcategoria, nextActive),
    });
  }

  async function executeConfirmAction() {
    if (!confirmAction) return;
    setIsConfirming(true);
    try {
      await confirmAction.run();
      setConfirmAction(null);
      await loadCategories();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo completar la operación"));
    } finally {
      setIsConfirming(false);
    }
  }

  function handleSaved() {
    setModal(null);
    loadCategories();
  }

  return (
    <div className="space-y-5">
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>

      <Panel className="overflow-hidden">
        <PanelToolbar
          search={
            <SearchBox
              label="Buscar categorías y subcategorías"
              placeholder="Buscar categoría o subcategoría..."
              value={searchQuery}
              onChange={setSearchQuery}
            />
          }
          actions={puedeCrear ? (
            <AdminActionButton
              icon={<PlusIcon />}
              variant="primary"
              onClick={() => setModal({ type: "category-create" })}
            >
              Nueva categoría
            </AdminActionButton>
          ) : null}
          meta={`${totals.categorias} categorías · ${totals.subcategorias} subcategorías`}
        />

        {isLoading ? (
          <p className={`p-8 text-center ${text.empty}`}>
            Cargando categorías...
          </p>
        ) : filteredCategories.length ? (
          <>
            <div className="space-y-3 p-4">
              {paginatedCategories.map((category) => (
                <CategoryCard
                  key={category.id_categoria}
                  category={category}
                  subcategorias={category.subcategoriasVisibles}
                  expanded={expandedIds.has(category.id_categoria)}
                  onAddSubcategory={puedeCrear ? () => setModal({ type: "subcategory-create", category }) : undefined}
                  onDeleteCategory={puedeEliminar ? () => requestDeleteCategory(category) : undefined}
                  onDeleteSubcategory={puedeEliminar ? requestDeleteSubcategory : undefined}
                  onEditCategory={puedeActualizar ? () => setModal({ type: "category-edit", category }) : undefined}
                  onEditSubcategory={puedeActualizar ? (subcategory) =>
                    setModal({ type: "subcategory-edit", category, subcategory })
                  : undefined}
                  onToggleCategoryStatus={puedeActualizar ? () => requestToggleCategory(category) : undefined}
                  onToggleSubcategoryStatus={puedeActualizar ? requestToggleSubcategory : undefined}
                  onToggle={() => toggleCategory(category.id_categoria)}
                />
              ))}
            </div>
            <Pagination
              page={page}
              pageSize={PAGE_SIZE}
              total={filteredCategories.length}
              onPageChange={setPage}
            />
          </>
        ) : categories.length ? (
          <p className={`p-8 text-center ${text.empty}`}>
            No hay resultados para la búsqueda.
          </p>
        ) : (
          <div className="p-8 text-center">
            <p className={text.empty}>
              No hay categorías registradas.
            </p>
            {puedeCrear ? (
              <div className="mt-4">
              <AdminActionButton
                icon={<PlusIcon />}
                variant="primary"
                onClick={() => setModal({ type: "category-create" })}
              >
                Nueva categoría
              </AdminActionButton>
              </div>
            ) : null}
          </div>
        )}
      </Panel>

      {modal?.type === "category-create" ? (
        <CategoryFormModal mode="create" onClose={() => setModal(null)} onSaved={handleSaved} />
      ) : null}

      {modal?.type === "category-edit" ? (
        <CategoryFormModal
          category={modal.category}
          mode="edit"
          onClose={() => setModal(null)}
          onSaved={handleSaved}
        />
      ) : null}

      {modal?.type === "subcategory-create" ? (
        <SubcategoryFormModal
          categories={categories}
          category={modal.category}
          onClose={() => setModal(null)}
          onSaved={handleSaved}
        />
      ) : null}

      {modal?.type === "subcategory-edit" ? (
        <SubcategoryFormModal
          categories={categories}
          category={modal.category}
          subcategory={modal.subcategory}
          onClose={() => setModal(null)}
          onSaved={handleSaved}
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
