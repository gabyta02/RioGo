import { useEffect, useState } from "react";
import { AdminActionButton, FormField, formInputClass, TimedAlert } from "./AdminControls";
import { getApiErrorMessage } from "../api/errors";
import { reenviarCodigoAdmin, solicitarCodigoAdmin } from "../auth/authService";
import { solicitarCodigoVerificacion } from "../../modules/profile/profileService";

const RESEND_SECONDS = 60;
const CODE_EXPIRES_MINUTES = 10;

export default function VerificationCodeFlow({
  error = "",
  onDismissError,
  onTokenChange,
  proposito = "actualizar_credenciales",
  username,
}) {
  const [codigo, setCodigo] = useState("");
  const [tokenVerificacion, setTokenVerificacion] = useState("");
  const [localError, setLocalError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);

  useEffect(() => {
    onTokenChange?.({ codigo_verificacion: codigo, token_verificacion: tokenVerificacion });
  }, [codigo, tokenVerificacion, onTokenChange]);

  useEffect(() => {
    if (!secondsLeft) return undefined;
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => (current > 0 ? current - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [secondsLeft]);

  async function handleSendCode() {
    if (!username) {
      setLocalError("No se pudo identificar el usuario");
      return;
    }
    setIsSending(true);
    setLocalError("");
    onDismissError?.();
    try {
      const response = proposito === "login_2fa"
        ? await solicitarCodigoAdmin(username)
        : await solicitarCodigoVerificacion({ proposito, username });
      setTokenVerificacion(response.token_verificacion);
      setSecondsLeft(RESEND_SECONDS);
    } catch (err) {
      setLocalError(getApiErrorMessage(err, "No se pudo enviar el código"));
    } finally {
      setIsSending(false);
    }
  }

  async function handleResend() {
    if (!username || secondsLeft > 0) return;
    setIsSending(true);
    setLocalError("");
    try {
      const response = proposito === "login_2fa"
        ? await reenviarCodigoAdmin(username)
        : await solicitarCodigoVerificacion({ proposito, username });
      setTokenVerificacion(response.token_verificacion);
      setSecondsLeft(RESEND_SECONDS);
    } catch (err) {
      setLocalError(getApiErrorMessage(err, "No se pudo reenviar el código"));
    } finally {
      setIsSending(false);
    }
  }

  const displayError = error || localError;

  return (
    <div className="space-y-3 rounded-lg border border-app-borde bg-app-fondo p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-app-texto-secundario">
          Verificación por correo electrónico
        </p>
        <AdminActionButton disabled={isSending || !username} onClick={handleSendCode}>
          {isSending ? "Enviando..." : tokenVerificacion ? "Reenviar código" : "Enviar código"}
        </AdminActionButton>
      </div>
      <TimedAlert onDismiss={() => setLocalError("")}>{displayError}</TimedAlert>
      <p className="text-xs font-semibold text-app-texto-secundario">
        El código expira en {CODE_EXPIRES_MINUTES} minutos.
      </p>
      <FormField label="Código de verificación">
        <input
          className={formInputClass}
          inputMode="numeric"
          maxLength={6}
          placeholder="123456"
          value={codigo}
          onChange={(event) => setCodigo(event.target.value.replace(/\D/g, "").slice(0, 6))}
        />
      </FormField>
      {secondsLeft > 0 ? (
        <p className="text-xs font-semibold text-app-texto-secundario">
          Puedes reenviar el código en {secondsLeft}s
        </p>
      ) : tokenVerificacion ? (
        <button
          className="text-xs font-black text-app-primario hover:underline"
          type="button"
          onClick={handleResend}
        >
          Reenviar código
        </button>
      ) : null}
    </div>
  );
}
