export default function AuthLayout({ children }) {
  return (
    <main className="min-h-screen bg-app-fondo px-5 py-8 text-app-texto-primario">
      <section className="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl items-center justify-center">
        {children}
      </section>
    </main>
  );
}
