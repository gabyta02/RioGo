export default function Panel({ children, className = "" }) {
  return (
    <section className={`rounded-lg border border-app-borde bg-app-tarjeta shadow-sm ${className}`}>
      {children}
    </section>
  );
}
