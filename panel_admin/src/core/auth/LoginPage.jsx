import { useState } from "react";
import AuthLayout from "../layouts/AuthLayout";
import PasswordInput from "../ui/PasswordInput";
import PrimaryButton from "../ui/PrimaryButton";
import TextInput from "../ui/TextInput";
import { LockIcon, UserIcon } from "../ui/icons";
import { getApiErrorMessage, needsTwoFactorCode } from "../api/errors";
import { loginUsuario, solicitarCodigoAdmin } from "./authService";
import { esSesionPanel } from "./authStorage";

const logoSrc = `${import.meta.env.BASE_URL}assets/logo.png`;

export default function LoginPage({ notice = "", onLoginSuccess, onVerificationRequired }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const username = form.username.trim();
    const password = form.password.trim();
    if (!username && !password) {
      setError("Ingresa tu nombre de usuario y contraseña.");
      return;
    }
    if (!username) {
      setError("Ingresa tu nombre de usuario.");
      return;
    }
    if (!password) {
      setError("Ingresa tu contraseña.");
      return;
    }

    setIsSubmitting(true);

    try {
      const session = await loginUsuario({ username, password });
      if (!esSesionPanel(session)) {
        setError("Esta cuenta no tiene acceso al panel administrativo");
        return;
      }
      onLoginSuccess(session);
    } catch (err) {
      if (needsTwoFactorCode(err)) {
        try {
          const response = await solicitarCodigoAdmin(username);
          onVerificationRequired({
            password,
            tokenVerificacion: response.token_verificacion,
            username,
          });
        } catch (verificationError) {
          setError(getApiErrorMessage(verificationError, "No se pudo enviar el código de verificación"));
        }
      } else {
        if (err?.response?.status === 401) {
          setForm((current) => ({ ...current, password: "" }));
        }
        setError(getApiErrorMessage(err, "No se pudo iniciar sesión"));
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <AuthLayout>
      <div className="w-full max-w-[360px] rounded-[28px] border border-app-borde bg-app-tarjeta px-6 py-8 shadow-[0_24px_70px_rgba(15,23,42,0.12)] sm:px-8">
        <img
          className="mx-auto flex h-32 w-32 rounded-full object-cover"
          src={logoSrc}
          alt="RiobambaTour"
        />

        <h1 className="mt-6 text-center text-xl font-semibold tracking-normal text-app-texto-primario">
          Bienvenido a RioGo
        </h1>

        {notice ? (
          <div className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-center text-sm font-semibold text-amber-900">
            {notice}
          </div>
        ) : null}

        <form
          className="mt-7 space-y-4"
          aria-label="Formulario de inicio de sesión"
          onSubmit={handleSubmit}
        >
          <TextInput
            autoComplete="username"
            disabled={isSubmitting}
            icon={<UserIcon />}
            label="Nombre de usuario"
            name="username"
            value={form.username}
            onChange={(event) => updateForm("username", event.target.value)}
            placeholder="Nombre de usuario"
          />

          <PasswordInput
            autoComplete="current-password"
            disabled={isSubmitting}
            icon={<LockIcon />}
            label="Contraseña"
            name="password"
            value={form.password}
            onChange={(event) => updateForm("password", event.target.value)}
            placeholder="Contraseña"
          />

          <div className="min-h-5 text-center text-sm font-semibold text-app-error">
            {error}
          </div>

          <PrimaryButton type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Validando..." : "Iniciar sesión"}
          </PrimaryButton>
        </form>
        <div className="mt-5 text-center">
          <p className="text-sm font-semibold text-app-texto-secundario">
            ¿Tienes problemas con el inicio de sesión?
          </p>
          <a
            className="mt-2 block text-sm font-black text-app-primario hover:underline"
            href="/account/"
          >
            Recuperar cuenta
          </a>
        </div>
      </div>
    </AuthLayout>
  );
}
