import { useEffect, useRef, useState } from "react";
import AuthLayout from "../layouts/AuthLayout";
import PrimaryButton from "../ui/PrimaryButton";
import { getApiErrorMessage } from "../api/errors";
import { loginUsuario, reenviarCodigoAdmin } from "./authService";
import { esSesionPanel } from "./authStorage";

const logoSrc = `${import.meta.env.BASE_URL}assets/logo.png`;
const CODE_EXPIRES_MINUTES = 10;

export default function VerificationCodePage({
  password,
  tokenVerificacion,
  username,
  onBack,
  onLoginSuccess,
  onTokenRefresh,
}) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [isVerifying, setIsVerifying] = useState(false);
  const [isResending, setIsResending] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (code.length !== 6) {
      return;
    }

    let isActive = true;

    async function verifyCode() {
      setIsVerifying(true);
      setError("");

      try {
        const session = await loginUsuario({
          username,
          password,
          codigo_verificacion: code,
          token_verificacion: tokenVerificacion,
        });

        if (!isActive) {
          return;
        }

        if (!esSesionPanel(session)) {
          setError("Esta cuenta no tiene acceso al panel administrativo");
          setCode("");
          inputRef.current?.focus();
          return;
        }

        onLoginSuccess(session);
      } catch (err) {
        if (isActive) {
          setError(getApiErrorMessage(err, "No se pudo completar la verificación"));
          setCode("");
          inputRef.current?.focus();
        }
      } finally {
        if (isActive) {
          setIsVerifying(false);
        }
      }
    }

    verifyCode();

    return () => {
      isActive = false;
    };
  }, [code, onLoginSuccess, password, tokenVerificacion, username]);

  async function handleResend() {
    setIsResending(true);
    setError("");

    try {
      const response = await reenviarCodigoAdmin(username);
      onTokenRefresh(response.token_verificacion);
      setCode("");
      inputRef.current?.focus();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo reenviar el código"));
    } finally {
      setIsResending(false);
    }
  }

  return (
    <AuthLayout>
      <div className="w-full max-w-[360px] rounded-[28px] border border-app-borde bg-app-tarjeta px-6 py-8 shadow-[0_24px_70px_rgba(15,23,42,0.12)] sm:px-8">
        <img
          className="mx-auto h-28 w-28 rounded-full object-cover"
          src={logoSrc}
          alt="RiobambaTour"
        />

        <h1 className="mt-6 text-center text-xl font-semibold tracking-normal text-app-texto-primario">
          Verificación de administrador
        </h1>

        <p className="mt-2 text-center text-sm font-medium text-app-texto-secundario">
          Ingresa el código enviado a tu correo.
        </p>
        <p className="mt-2 text-center text-xs font-semibold text-app-texto-secundario">
          El código expira en {CODE_EXPIRES_MINUTES} minutos y se verificará automáticamente al completar los 6 dígitos.
        </p>

        <label className="mt-7 block">
          <span className="sr-only">Código de verificación</span>
          <input
            ref={inputRef}
            className="h-16 w-full rounded-2xl border border-app-borde bg-app-tarjeta px-4 text-center text-2xl font-bold tracking-[0.45em] text-app-texto-primario shadow-sm outline-none transition placeholder:tracking-normal placeholder:text-app-texto-secundario focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
            value={code}
            onChange={(event) => {
              const nextCode = event.target.value.replace(/\D/g, "").slice(0, 6);
              setCode(nextCode);
            }}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            disabled={isVerifying}
          />
        </label>

        <div className="mt-4 min-h-6 text-center text-sm font-semibold">
          {isVerifying ? (
            <span className="text-app-texto-secundario">Verificando código...</span>
          ) : error ? (
            <span className="text-app-error">{error}</span>
          ) : null}
        </div>

        <div className="mt-4 space-y-3">
          <PrimaryButton
            type="button"
            variant="secondary"
            disabled={isResending || isVerifying}
            onClick={handleResend}
          >
            {isResending ? "Reenviando..." : "Reenviar código"}
          </PrimaryButton>
          <button
            className="h-11 w-full rounded-2xl text-sm font-bold text-app-texto-secundario transition hover:bg-app-primario-claro hover:text-app-primario focus:outline-none focus:ring-4 focus:ring-app-primario-claro"
            type="button"
            onClick={onBack}
            disabled={isVerifying || isResending}
          >
            Volver al login
          </button>
        </div>
      </div>
    </AuthLayout>
  );
}
