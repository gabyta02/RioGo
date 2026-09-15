function getVisiblePages(page, totalPages, maxVisible = 5) {
  if (totalPages <= maxVisible) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  let start = Math.max(1, page - Math.floor(maxVisible / 2));
  let end = Math.min(totalPages, start + maxVisible - 1);
  start = Math.max(1, end - maxVisible + 1);

  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

const noop = () => {};

export default function Pagination({ page, pageSize, total, onPageChange }) {
  const totalPages = Math.max(Math.ceil(total / pageSize), 1);
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const visiblePages = getVisiblePages(page, totalPages);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-app-borde px-4 py-3 text-sm">
      <p className="font-semibold text-app-texto-secundario">
        Mostrando {from}-{to} de {total} registros
      </p>
      <div className="flex items-center gap-2">
        <button
          className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario transition hover:bg-app-fondo disabled:opacity-50"
          type="button"
          disabled={page <= 1}
          onClick={() => (onPageChange || noop)(page - 1)}
        >
          Anterior
        </button>
        {visiblePages.map((pageNumber) => (
          <button
            key={pageNumber}
            className={`grid h-9 min-w-9 place-items-center rounded-lg px-3 text-sm font-black transition ${
              pageNumber === page
                ? "bg-app-primario text-white"
                : "border border-app-borde text-app-texto-secundario hover:bg-app-fondo"
            }`}
            type="button"
            onClick={() => (onPageChange || noop)(pageNumber)}
          >
            {pageNumber}
          </button>
        ))}
        <button
          className="h-9 rounded-lg border border-app-borde px-3 font-bold text-app-texto-secundario transition hover:bg-app-fondo disabled:opacity-50"
          type="button"
          disabled={page >= totalPages}
          onClick={() => (onPageChange || noop)(page + 1)}
        >
          Siguiente
        </button>
      </div>
    </div>
  );
}
