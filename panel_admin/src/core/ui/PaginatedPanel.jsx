import Pagination from "./Pagination";

const noop = () => {};

export function CompactPager({ noun = "Hoja", onPageChange, page, total }) {
  if (total <= 1) {
    return null;
  }

  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-t border-app-borde px-4 py-2 text-sm">
      <button
        className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario transition hover:bg-app-fondo disabled:opacity-50"
        type="button"
        disabled={page <= 1}
        onClick={() => (onPageChange || noop)(page - 1)}
      >
        Anterior
      </button>
      <p className="font-black text-app-texto-primario">
        {noun} {page} de {total}
      </p>
      <button
        className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario transition hover:bg-app-fondo disabled:opacity-50"
        type="button"
        disabled={page >= total}
        onClick={() => (onPageChange || noop)(page + 1)}
      >
        Siguiente
      </button>
    </div>
  );
}

export default function PaginatedPanel({
  children,
  emptyMessage = "No hay elementos.",
  itemCount,
  page,
  pageSize,
  onPageChange,
}) {
  const total = itemCount ?? 0;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-hidden">
        {total ? (
          <div className="h-full space-y-2">{children}</div>
        ) : (
          <div className="grid h-full place-items-center rounded-lg border border-dashed border-app-borde p-4 text-center text-sm font-semibold text-app-texto-secundario">
            {emptyMessage}
          </div>
        )}
      </div>
      {total > pageSize ? (
        <div className="mt-2 shrink-0 overflow-hidden rounded-lg border border-app-borde bg-app-tarjeta">
          <Pagination page={page} pageSize={pageSize} total={total} onPageChange={onPageChange} />
        </div>
      ) : null}
    </div>
  );
}
