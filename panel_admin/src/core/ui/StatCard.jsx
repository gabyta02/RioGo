export default function StatCard({ icon, label, loading = false, value }) {
  return (
    <section className="min-h-[116px] rounded-lg border border-app-borde bg-app-tarjeta p-4 shadow-sm">
      <div className="flex items-start">
        <div className="grid h-9 w-9 place-items-center rounded-lg bg-app-primario-claro text-app-primario">
          {icon}
        </div>
      </div>
      <p className="mt-5 text-2xl font-black leading-none text-app-texto-primario">
        {loading ? "..." : value}
      </p>
      <p className="mt-2 text-sm font-medium text-app-texto-secundario">{label}</p>
    </section>
  );
}
