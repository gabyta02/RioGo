import { useEffect, useState } from "react";
import {
  AdminActionButton,
  FormField,
  TimedAlert,
  Toggle,
  formInputClass,
} from "../../core/ui/AdminControls";
import CollapsibleSection from "../../core/ui/CollapsibleSection";
import VerificationCodePanel from "../../core/ui/VerificationCodePanel";
import { getApiErrorMessage } from "../../core/api/errors";
import { actualizar2FA } from "./profileService";

export default function SecurityTab({ onSaved, perfil }) {
  const [expanded, setExpanded] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(Boolean(perfil?.autentificacion_doble));
  const [pendingTwoFactor, setPendingTwoFactor] = useState(null);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    setTwoFactorEnabled(Boolean(perfil?.autentificacion_doble));
    setPendingTwoFactor(null);
    setPhase("idle");
    setPassword("");
  }, [perfil?.autentificacion_doble, perfil?.username]);

  function handleToggle(nextValue) {
    if (nextValue === Boolean(perfil?.autentificacion_doble)) {
      setPendingTwoFactor(null);
      setPhase("idle");
      setPassword("");
      return;
    }
    setPendingTwoFactor(nextValue);
    setTwoFactorEnabled(nextValue);
    setPhase("form");
    setError("");
    setSuccess("");
  }

  function handleStartVerification(event) {
    event.preventDefault();
    if (!password) {
      setError("Ingresa tu contraseña actual");
      return;
    }
    if (pendingTwoFactor === null) {
      setError("Selecciona activar o desactivar la autenticación en dos pasos");
      return;
    }
    setError("");
    setPhase("verify");
  }

  async function handleVerify(verification) {
    setIsSaving(true);
    setError("");
    try {
      await actualizar2FA({
        username: perfil.username,
        password,
        autentificacion_doble: pendingTwoFactor,
        ...verification,
      });
      setSuccess(pendingTwoFactor
        ? "Autenticación en dos pasos activada"
        : "Autenticación en dos pasos desactivada");
      setPendingTwoFactor(null);
      setPhase("idle");
      setPassword("");
      onSaved?.();
    } catch (err) {
      setTwoFactorEnabled(Boolean(perfil?.autentificacion_doble));
      setPendingTwoFactor(null);
      setPhase("idle");
      setError(getApiErrorMessage(err, "No se pudo actualizar la autenticación en dos pasos"));
    } finally {
      setIsSaving(false);
    }
  }

  function handleCancel() {
    setTwoFactorEnabled(Boolean(perfil?.autentificacion_doble));
    setPendingTwoFactor(null);
    setPhase("idle");
    setPassword("");
    setError("");
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-black text-app-texto-primario">Seguridad</h3>
        <p className="mt-1 text-sm font-semibold text-app-texto-secundario">
          Configura la autenticación en dos pasos para proteger tu cuenta.
        </p>
      </div>

      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <TimedAlert variant="success" onDismiss={() => setSuccess("")}>{success}</TimedAlert>

      <CollapsibleSection
        description={
          twoFactorEnabled
            ? "La verificación por correo está activa al iniciar sesión."
            : "Activa un código por correo al iniciar sesión."
        }
        expanded={expanded}
        title="Autenticación en dos pasos"
        onToggle={() => setExpanded((current) => !current)}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4 rounded-lg border border-app-borde bg-app-tarjeta p-4">
            <div>
              <p className="text-sm font-black text-app-texto-primario">
                {twoFactorEnabled ? "2FA activada" : "2FA desactivada"}
              </p>
              <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
                Recibirás un código en tu correo al iniciar sesión.
              </p>
            </div>
            <Toggle
              checked={twoFactorEnabled}
              label="Activar autenticación en dos pasos"
              onChange={handleToggle}
            />
          </div>

          {phase === "verify" ? (
            <VerificationCodePanel
              description="Te enviamos un código a tu correo para confirmar el cambio de 2FA."
              error={error}
              isSubmitting={isSaving}
              username={perfil.username}
              onBack={() => setPhase("form")}
              onSubmit={handleVerify}
            />
          ) : pendingTwoFactor !== null ? (
            <form className="space-y-4" onSubmit={handleStartVerification}>
              <FormField label="Contraseña actual">
                <input
                  autoComplete="current-password"
                  className={formInputClass}
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </FormField>
              <div className="flex justify-end gap-2">
                <AdminActionButton onClick={handleCancel}>Cancelar</AdminActionButton>
                <AdminActionButton type="submit" variant="primary">
                  {pendingTwoFactor ? "Activar 2FA" : "Desactivar 2FA"}
                </AdminActionButton>
              </div>
            </form>
          ) : (
            <p className="text-sm font-semibold text-app-texto-secundario">
              Usa el interruptor para activar o desactivar la verificación en dos pasos.
            </p>
          )}
        </div>
      </CollapsibleSection>
    </div>
  );
}
