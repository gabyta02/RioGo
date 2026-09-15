import { useEffect, useState } from "react";
import TabGroup from "../../core/ui/TabGroup";
import { TimedAlert } from "../../core/ui/AdminControls";
import { getApiErrorMessage } from "../../core/api/errors";
import { actualizarPermisosSesion } from "../../core/auth/authStorage";
import { obtenerPerfil } from "./profileService";
import ProfileTab from "./ProfileTab";
import SecurityTab from "./SecurityTab";

const TABS = [
  { id: "perfil", label: "Perfil" },
  { id: "seguridad", label: "Seguridad" },
];

export default function ProfileSettingsModal({ onClose, onLogout, onSessionUpdated }) {
  const [activeTab, setActiveTab] = useState("perfil");
  const [perfil, setPerfil] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  async function loadPerfil() {
    setIsLoading(true);
    setError("");
    try {
      const data = await obtenerPerfil();
      setPerfil(data);
      const sesion = actualizarPermisosSesion(data);
      onSessionUpdated?.(sesion);
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo cargar el perfil"));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadPerfil();
  }, []);

  function handleSaved() {
    loadPerfil();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/30 p-4">
      <div className="w-full max-w-3xl overflow-hidden rounded-lg bg-app-tarjeta shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-app-borde px-5 pt-5">
          <div>
            <h2 className="text-lg font-black text-app-texto-primario">Mi perfil</h2>
            <p className="mt-1 text-sm font-semibold text-app-texto-secundario">
              Administra tu cuenta y la seguridad de acceso.
            </p>
          </div>
          <button
            className="grid h-8 w-8 place-items-center rounded-lg text-xl leading-none text-app-texto-primario transition hover:bg-app-fondo"
            type="button"
            onClick={onClose}
            aria-label="Cerrar"
          >
            ×
          </button>
        </div>

        <div className="px-5 pt-4">
          <TabGroup activeId={activeTab} tabs={TABS} onChange={setActiveTab} />
        </div>

        <div className="space-y-4 px-5 py-5">
          <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
          {isLoading ? (
            <div className="grid min-h-[280px] place-items-center text-sm font-semibold text-app-texto-secundario">
              Cargando perfil...
            </div>
          ) : perfil ? (
            activeTab === "perfil" ? (
              <ProfileTab perfil={perfil} onLogout={onLogout} onSaved={handleSaved} />
            ) : (
              <SecurityTab perfil={perfil} onSaved={handleSaved} />
            )
          ) : null}
        </div>
      </div>
    </div>
  );
}
