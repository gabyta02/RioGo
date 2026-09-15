import { useEffect, useRef, useState } from "react";
import AuthLayout from "../layouts/AuthLayout";
import PasswordInput from "../ui/PasswordInput";
import PrimaryButton from "../ui/PrimaryButton";
import TextInput from "../ui/TextInput";
import { LockIcon, UserIcon } from "../ui/icons";
import { getApiErrorMessage } from "../api/errors";
import {
  confirmarRecuperacionPassword,
  solicitarRecuperacionPassword,
  solicitarRecordatorioUsuario,
} from "./authService";

const logoSrc = `${import.meta.env.BASE_URL}assets/logo.png`;

function AccountTab({ active, children, onClick }) {
  return (
    <button
      className={`h-10 flex-1 rounded-lg px-3 text-sm font-black transition focus:outline-none focus:ring-4 focus:ring-app-primario-claro ${
        active
          ? "bg-app-primario text-white"
          : "bg-app-fondo text-app-texto-secundario hover:text-app-primario"
      }`}
      type="button"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function Alert({ children, variant = "error" }) {
  if (!children) return null;
  const className = variant === "success"
    ? "border-app-exito-borde bg-app-exito-fondo text-app-primario"
    : "border-app-error bg-app-error-fondo text-app-error";
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm font-bold ${className}`} role="status">
      {children}
    </div>
  );
}

function PasswordRecoveryForm() {
  const [step, setStep] = useState("form");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [tokenVerificacion, setTokenVerificacion] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isRequestingCode, setIsRequestingCode] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);

  const codeInputRef = useRef(null);

  useEffect(() => {
    if (step === "code") {
      codeInputRef.current?.focus();
    }
  }, [step]);

  async function requestCode() {
    setError("");
    setSuccess("");
    const emailValue = email.trim();
    setIsRequestingCode(true);
    try {
      const response = await solicitarRecuperacionPassword(emailValue);
      setTokenVerificacion(response.token_verificacion || "");
      setCode("");
      setStep("code");
      setSuccess(response.mensaje || "Revisa tu correo para continuar.");
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo solicitar la recuperación"));
    } finally {
      setIsRequestingCode(false);
    }
  }

  function validatePasswordForm() {
    const emailValue = email.trim();
    if (!emailValue || !password || !confirmPassword) {
      setError("Completa todos los campos.");
      return false;
    }
    if (password.length < 6) {
      setError("La nueva contraseña debe tener al menos 6 caracteres.");
      return false;
    }
    if (password !== confirmPassword) {
      setError("La confirmación no coincide.");
      return false;
    }
    return true;
  }

  async function handleRequestCode(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    if (!validatePasswordForm()) {
      return;
    }
    await requestCode();
  }

  async function handleConfirm(nextCode = code) {
    setError("");
    const emailValue = email.trim();
    if (!emailValue || !nextCode || !password || !confirmPassword) {
      setError("Completa todos los campos.");
      return;
    }
    if (password !== confirmPassword) {
      setError("La confirmación no coincide.");
      return;
    }
    if (!tokenVerificacion) {
      setError("Solicita primero un código de recuperación.");
      return;
    }
    setIsConfirming(true);
    try {
      const response = await confirmarRecuperacionPassword({
        email: emailValue,
        nuevo_password: password,
        codigo_verificacion: nextCode,
        token_verificacion: tokenVerificacion,
      });
      setCode("");
      setPassword("");
      setConfirmPassword("");
      setStep("form");
      setSuccess(response.mensaje || "Tu contraseña fue actualizada.");
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo cambiar la contraseña"));
      setCode("");
      codeInputRef.current?.focus();
    } finally {
      setIsConfirming(false);
    }
  }

  useEffect(() => {
    if (step !== "code" || code.length !== 6 || isConfirming) {
      return;
    }

    handleConfirm(code);
  }, [code, isConfirming, step]);

  if (step === "code") {
    return (
      <div className="space-y-4">
        <p className="text-center text-sm font-medium text-app-texto-secundario">
          Ingresa el código enviado a tu correo.
        </p>
        <p className="text-center text-xs font-semibold text-app-texto-secundario">
          Se validará automáticamente al completar los 6 dígitos.
        </p>

        <label className="block">
          <span className="sr-only">Código de verificación</span>
          <input
            ref={codeInputRef}
            className="h-16 w-full rounded-2xl border border-app-borde bg-app-tarjeta px-4 text-center text-2xl font-bold tracking-[0.45em] text-app-texto-primario shadow-sm outline-none transition placeholder:tracking-normal placeholder:text-app-texto-secundario focus:border-app-primario focus:ring-4 focus:ring-app-primario-claro"
            value={code}
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            placeholder="000000"
            disabled={isConfirming}
          />
        </label>

        <Alert>{error}</Alert>
        <Alert variant="success">{success}</Alert>
        {isConfirming ? (
          <p className="text-center text-sm font-semibold text-app-texto-secundario">
            Verificando código...
          </p>
        ) : null}

        <PrimaryButton
          type="button"
          variant="secondary"
          disabled={isRequestingCode || isConfirming}
          onClick={requestCode}
        >
          {isRequestingCode ? "Reenviando..." : "Reenviar código"}
        </PrimaryButton>
        <button
          className="h-11 w-full rounded-2xl text-sm font-bold text-app-texto-secundario transition hover:bg-app-primario-claro hover:text-app-primario focus:outline-none focus:ring-4 focus:ring-app-primario-claro"
          type="button"
          onClick={() => {
            setCode("");
            setError("");
            setStep("form");
          }}
          disabled={isRequestingCode || isConfirming}
        >
          Cambiar datos
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <form className="space-y-4" onSubmit={handleRequestCode}>
        <TextInput
          autoComplete="email"
          disabled={isRequestingCode}
          icon={<UserIcon />}
          label="Correo electrónico"
          name="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Correo electrónico"
          type="email"
        />
        <PasswordInput
          autoComplete="new-password"
          disabled={isRequestingCode}
          icon={<LockIcon />}
          label="Nueva contraseña"
          name="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="Nueva contraseña"
        />
        <PasswordInput
          autoComplete="new-password"
          disabled={isRequestingCode}
          icon={<LockIcon />}
          label="Confirmar contraseña"
          name="confirmPassword"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          placeholder="Confirmar contraseña"
        />
        <Alert>{error}</Alert>
        <Alert variant="success">{success}</Alert>
        <PrimaryButton type="submit" disabled={isRequestingCode}>
          {isRequestingCode ? "Enviando..." : "Enviar código"}
        </PrimaryButton>
      </form>
    </div>
  );
}

function UsernameReminderForm() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");
    const emailValue = email.trim();
    if (!emailValue) {
      setError("Ingresa tu correo electrónico.");
      return;
    }
    setIsSubmitting(true);
    try {
      const response = await solicitarRecordatorioUsuario(emailValue);
      setSuccess(response.mensaje || "Revisa tu correo.");
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo procesar la solicitud"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <TextInput
        autoComplete="email"
        disabled={isSubmitting}
        icon={<UserIcon />}
        label="Correo electrónico"
        name="emailRecordatorio"
        value={email}
        onChange={(event) => setEmail(event.target.value)}
        placeholder="Correo electrónico"
        type="email"
      />
      <Alert>{error}</Alert>
      <Alert variant="success">{success}</Alert>
      <PrimaryButton type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Enviando..." : "Enviar usuario"}
      </PrimaryButton>
    </form>
  );
}

export default function AccountRecoveryPage() {
  const [activeTab, setActiveTab] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get("modo") === "username" ? "username" : "password";
  });

  return (
    <AuthLayout>
      <div className="w-full max-w-[420px] rounded-[28px] border border-app-borde bg-app-tarjeta px-6 py-8 shadow-[0_24px_70px_rgba(15,23,42,0.12)] sm:px-8">
        <img
          className="mx-auto flex h-28 w-28 rounded-full object-cover"
          src={logoSrc}
          alt="RioGo"
        />
        <h1 className="mt-6 text-center text-xl font-semibold tracking-normal text-app-texto-primario">
          Cuenta RioGo
        </h1>

        <div className="mt-7 flex gap-2 rounded-xl bg-app-fondo p-1">
          <AccountTab active={activeTab === "password"} onClick={() => setActiveTab("password")}>
            Cambiar contraseña
          </AccountTab>
          <AccountTab active={activeTab === "username"} onClick={() => setActiveTab("username")}>
            Consultar usuario
          </AccountTab>
        </div>

        <div className="mt-6">
          {activeTab === "password" ? <PasswordRecoveryForm /> : <UsernameReminderForm />}
        </div>
      </div>
    </AuthLayout>
  );
}
