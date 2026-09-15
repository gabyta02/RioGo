import { useEffect, useRef, useState } from "react";
import { AdminActionButton, FormField, TimedAlert, formInputClass } from "./AdminControls";
import { getApiErrorMessage } from "../api/errors";
import { reenviarCodigoVerificacion, solicitarCodigoVerificacion } from "../../modules/profile/profileService";

const RESEND_SECONDS = 60;
const CODE_EXPIRES_MINUTES = 10;

export default function VerificationCodePanel({
  description = "Ingresa el código enviado a tu correo para confirmar el cambio.",
  error = "",
  isSubmitting = false,
  onBack,
  onSubmit,
  proposito = "actualizar_credenciales",
  title = "Verificación por correo",
  tokenVerificacion: initialToken = "",
  username,
}) {
  const inputRef = useRef(null);
  const [codigo, setCodigo] = useState("");
  const [tokenVerificacion, setTokenVerificacion] = useState(initialToken);
  const [localError, setLocalError] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const lastSubmittedCodeRef = useRef("");

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (initialToken) {
      setTokenVerificacion(initialToken);
      return;
    }
    if (!username) return;

    let isActive = true;
    async function sendInitialCode() {
      setIsSending(true);
      setLocalError("");
      try {
        const response = await solicitarCodigoVerificacion({ proposito, username });
        if (isActive) {
          setTokenVerificacion(response.token_verificacion);
          setSecondsLeft(RESEND_SECONDS);
        }
      } catch (err) {
        if (isActive) {
          setLocalError(getApiErrorMessage(err, "No se pudo enviar el código"));
        }
      } finally {
        if (isActive) {
          setIsSending(false);
        }
      }
    }

    sendInitialCode();
    return () => {
      isActive = false;
    };
  }, [initialToken, proposito, username]);

  useEffect(() => {
    if (!secondsLeft) return undefined;
    const timer = window.setInterval(() => {
      setSecondsLeft((current) => (current > 0 ? current - 1 : 0));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [secondsLeft]);

  useEffect(() => {
    if (
      codigo.length !== 6
      || !tokenVerificacion
      || isSubmitting
      || isSending
      || lastSubmittedCodeRef.current === codigo
    ) {
      return;
    }

    lastSubmittedCodeRef.current = codigo;
    setLocalError("");
    onSubmit?.({ codigo_verificacion: codigo, token_verificacion: tokenVerificacion });
  }, [codigo, isSending, isSubmitting, onSubmit, tokenVerificacion]);

  async function handleResend() {
    if (!username || secondsLeft > 0 || isSending) return;
    setIsSending(true);
    setLocalError("");
    try {
      const response = await reenviarCodigoVerificacion({ proposito, username });
      setTokenVerificacion(response.token_verificacion);
      setSecondsLeft(RESEND_SECONDS);
      setCodigo("");
      lastSubmittedCodeRef.current = "";
      inputRef.current?.focus();
    } catch (err) {
      setLocalError(getApiErrorMessage(err, "No se pudo reenviar el código"));
    } finally {
      setIsSending(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
  }

  const displayError = error || localError;

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div>
        <h4 className="text-sm font-black text-app-texto-primario">{title}</h4>
        <p className="mt-1 text-xs font-semibold text-app-texto-secundario">{description}</p>
        <p className="mt-1 text-xs font-semibold text-app-texto-secundario">
          El código expira en {CODE_EXPIRES_MINUTES} minutos. Se verificará automáticamente al completar los 6 dígitos.
        </p>
      </div>

      <TimedAlert onDismiss={() => setLocalError("")}>{displayError}</TimedAlert>

      {isSending && !tokenVerificacion ? (
        <p className="text-sm font-semibold text-app-texto-secundario">Enviando código a tu correo...</p>
      ) : null}

      <FormField label="Código de verificación">
        <input
          ref={inputRef}
          className={`${formInputClass} text-center text-lg font-black tracking-[0.35em]`}
          disabled={isSubmitting || isSending}
          inputMode="numeric"
          maxLength={6}
          placeholder="000000"
          value={codigo}
          onChange={(event) => {
            const nextCode = event.target.value.replace(/\D/g, "").slice(0, 6);
            if (nextCode.length < 6) {
              lastSubmittedCodeRef.current = "";
            }
            setCodigo(nextCode);
          }}
        />
      </FormField>

      <div className="flex flex-wrap items-center justify-between gap-2">
        {secondsLeft > 0 ? (
          <p className="text-xs font-semibold text-app-texto-secundario">
            Reenviar en {secondsLeft}s
          </p>
        ) : (
          <button
            className="text-xs font-black text-app-primario hover:underline disabled:opacity-50"
            disabled={isSending || isSubmitting}
            type="button"
            onClick={handleResend}
          >
            {isSending ? "Reenviando..." : "Reenviar código"}
          </button>
        )}
        <div className="flex gap-2">
          <AdminActionButton disabled={isSubmitting} onClick={onBack}>Volver</AdminActionButton>
        </div>
      </div>
    </form>
  );
}
