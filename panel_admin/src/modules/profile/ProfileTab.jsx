import { useEffect, useRef, useState } from "react";
import {
  AdminActionButton,
  FormField,
  TimedAlert,
  formInputClass,
} from "../../core/ui/AdminControls";
import CollapsibleSection from "../../core/ui/CollapsibleSection";
import ProfileAvatar, { getProfileInitials, resolveProfilePhotoUrl } from "../../core/ui/ProfileAvatar";
import ReadOnlyField, { ReadOnlyFieldGrid } from "../../core/ui/ReadOnlyField";
import VerificationCodePanel from "../../core/ui/VerificationCodePanel";
import { getApiErrorMessage } from "../../core/api/errors";
import { cerrarSesionLocal } from "../../core/api/client";
import { actualizarCuenta, subirFotoPerfil } from "./profileService";

const MAX_PHOTO_BYTES = 2 * 1024 * 1024;
const PASSWORD_FIELD_NAMES = {
  actual: "password",
  nuevo: "nuevo_password",
  confirmar: "confirmar_password",
};

const PASSWORD_FIELD_LABELS = {
  actual: "Contraseña actual",
  nuevo: "Nueva contraseña",
  confirmar: "Confirmar contraseña",
};

function rolLabel(rol) {
  if (rol === "super-admin") return "Super administrador";
  if (rol === "admin") return "Administrador";
  return rol || "Usuario";
}

function ChangeUsernamePanel({ onCancel, onSaved, perfil }) {
  const [nuevoUsername, setNuevoUsername] = useState(perfil?.username || "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!password) {
      setError("Ingresa tu contraseña actual");
      return;
    }
    if (nuevoUsername.trim() === perfil?.username) {
      setError("El nombre de usuario no cambió");
      return;
    }

    setIsSaving(true);
    setError("");
    try {
      await actualizarCuenta({
        username: perfil.username,
        password,
        nuevo_username: nuevoUsername.trim(),
      });
      onSaved?.();
      onCancel?.();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo actualizar el usuario"));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <FormField label="Nuevo nombre de usuario">
        <input
          className={formInputClass}
          value={nuevoUsername}
          onChange={(event) => setNuevoUsername(event.target.value)}
        />
      </FormField>
      <FormField label={PASSWORD_FIELD_LABELS.actual}>
        <input
          autoComplete="current-password"
          className={formInputClass}
          id="perfil-username-password"
          name={PASSWORD_FIELD_NAMES.actual}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </FormField>
      <div className="flex justify-end gap-2">
        <AdminActionButton onClick={onCancel}>Cancelar</AdminActionButton>
        <AdminActionButton disabled={isSaving} type="submit" variant="primary">
          {isSaving ? "Guardando..." : "Guardar usuario"}
        </AdminActionButton>
      </div>
    </form>
  );
}

function ChangeEmailPanel({ onCancel, onSaved, perfil }) {
  const [phase, setPhase] = useState("form");
  const [nuevoEmail, setNuevoEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleStartChange(event) {
    event.preventDefault();
    if (!password) {
      setError("Ingresa tu contraseña actual");
      return;
    }
    if (!nuevoEmail.trim()) {
      setError("Ingresa el nuevo correo electrónico");
      return;
    }
    setError("");
    setPhase("verify");
  }

  async function handleVerify(verification) {
    setIsSaving(true);
    setError("");
    try {
      await actualizarCuenta({
        username: perfil.username,
        password,
        nuevo_email: nuevoEmail.trim(),
        ...verification,
      });
      onSaved?.();
      onCancel?.();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo actualizar el correo"));
    } finally {
      setIsSaving(false);
    }
  }

  if (phase === "verify") {
    return (
      <VerificationCodePanel
        description="Te enviamos un código a tu correo actual. Ingrésalo para confirmar el cambio."
        error={error}
        isSubmitting={isSaving}
        username={perfil.username}
        onBack={() => setPhase("form")}
        onSubmit={handleVerify}
      />
    );
  }

  return (
    <form className="space-y-4" onSubmit={handleStartChange}>
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <FormField label="Correo actual">
        <input className={formInputClass} disabled readOnly value={perfil?.email || ""} />
      </FormField>
      <FormField label="Nuevo correo electrónico">
        <input
          className={formInputClass}
          type="email"
          value={nuevoEmail}
          onChange={(event) => setNuevoEmail(event.target.value)}
        />
      </FormField>
      <FormField label={PASSWORD_FIELD_LABELS.actual}>
        <input
          autoComplete="current-password"
          className={formInputClass}
          id="perfil-email-password"
          name={PASSWORD_FIELD_NAMES.actual}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </FormField>
      <div className="flex justify-end gap-2">
        <AdminActionButton onClick={onCancel}>Cancelar</AdminActionButton>
        <AdminActionButton type="submit" variant="primary">Enviar código</AdminActionButton>
      </div>
    </form>
  );
}

function ChangePasswordPanel({ onCancel, onLogout, onSaved, perfil }) {
  const [phase, setPhase] = useState("form");
  const [password, setPassword] = useState("");
  const [nuevoPassword, setNuevoPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function handleStartChange(event) {
    event.preventDefault();
    if (!password || !nuevoPassword || !confirmPassword) {
      setError("Completa la contraseña actual, la nueva y su confirmación");
      return;
    }
    if (nuevoPassword !== confirmPassword) {
      setError("La confirmación no coincide");
      return;
    }
    setError("");
    setPhase("verify");
  }

  async function handleVerify(verification) {
    setIsSaving(true);
    setError("");
    try {
      await actualizarCuenta({
        username: perfil.username,
        password,
        nuevo_password: nuevoPassword,
        ...verification,
      });
      onSaved?.();
      window.setTimeout(() => {
        cerrarSesionLocal();
        onLogout?.();
      }, 1200);
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo actualizar la contraseña"));
    } finally {
      setIsSaving(false);
    }
  }

  if (phase === "verify") {
    return (
      <VerificationCodePanel
        description="Te enviamos un código a tu correo. Confírmalo para aplicar la nueva contraseña."
        error={error}
        isSubmitting={isSaving}
        username={perfil.username}
        onBack={() => setPhase("form")}
        onSubmit={handleVerify}
      />
    );
  }

  return (
    <form className="space-y-4" onSubmit={handleStartChange}>
      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <FormField label={PASSWORD_FIELD_LABELS.actual}>
        <input
          autoComplete="current-password"
          className={formInputClass}
          id="perfil-password-actual"
          name={PASSWORD_FIELD_NAMES.actual}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </FormField>
      <FormField label={PASSWORD_FIELD_LABELS.nuevo}>
        <input
          autoComplete="new-password"
          className={formInputClass}
          id="perfil-password-nuevo"
          name={PASSWORD_FIELD_NAMES.nuevo}
          type="password"
          value={nuevoPassword}
          onChange={(event) => setNuevoPassword(event.target.value)}
        />
      </FormField>
      <FormField label={PASSWORD_FIELD_LABELS.confirmar}>
        <input
          autoComplete="new-password"
          className={formInputClass}
          id="perfil-password-confirmar"
          name={PASSWORD_FIELD_NAMES.confirmar}
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
        />
      </FormField>
      <div className="flex justify-end gap-2">
        <AdminActionButton onClick={onCancel}>Cancelar</AdminActionButton>
        <AdminActionButton type="submit" variant="primary">Enviar código</AdminActionButton>
      </div>
    </form>
  );
}

export default function ProfileTab({ onLogout, onSaved, perfil }) {
  const fileInputRef = useRef(null);
  const [openSection, setOpenSection] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [photoPreview, setPhotoPreview] = useState(resolveProfilePhotoUrl(perfil?.foto_url));

  useEffect(() => {
    setPhotoPreview(resolveProfilePhotoUrl(perfil?.foto_url));
  }, [perfil?.foto_url]);

  const displayName = perfil?.nombre_completo || perfil?.username || "Admin";
  const initials = getProfileInitials(displayName);

  function toggleSection(section) {
    setOpenSection((current) => (current === section ? null : section));
    setError("");
    setSuccess("");
  }

  async function handlePhotoChange(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!["image/jpeg", "image/png", "image/jpg"].includes(file.type)) {
      setError("Solo se permiten archivos JPG o PNG");
      return;
    }
    if (file.size > MAX_PHOTO_BYTES) {
      setError("La imagen no puede superar 2 MB");
      return;
    }

    setIsUploading(true);
    setError("");
    setSuccess("");
    try {
      const response = await subirFotoPerfil(file);
      setPhotoPreview(resolveProfilePhotoUrl(response.foto_url));
      setSuccess("Foto de perfil actualizada");
      onSaved?.();
    } catch (err) {
      setError(getApiErrorMessage(err, "No se pudo subir la foto"));
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  function handleSectionSaved() {
    setSuccess("Cambios guardados correctamente");
    setOpenSection(null);
    onSaved?.();
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-base font-black text-app-texto-primario">Ficha del usuario</h3>
        <p className="mt-1 text-sm font-semibold text-app-texto-secundario">
          Consulta tus datos administrativos. Los cambios se realizan en los apartados inferiores.
        </p>
      </div>

      <TimedAlert onDismiss={() => setError("")}>{error}</TimedAlert>
      <TimedAlert variant="success" onDismiss={() => setSuccess("")}>{success}</TimedAlert>

      <div className="rounded-lg border border-app-borde bg-app-fondo p-5">
        <div className="flex flex-wrap items-center gap-4 border-b border-app-borde pb-5">
          <ProfileAvatar initials={initials} name={displayName} size="xl" src={photoPreview} />
          <div>
            <input
              ref={fileInputRef}
              accept="image/jpeg,image/png"
              className="hidden"
              type="file"
              onChange={handlePhotoChange}
            />
            <AdminActionButton
              disabled={isUploading}
              onClick={() => fileInputRef.current?.click()}
            >
              {isUploading ? "Subiendo..." : "Cambiar foto"}
            </AdminActionButton>
            <p className="mt-2 text-xs font-semibold text-app-texto-secundario">JPG o PNG. Máx 2 MB.</p>
          </div>
        </div>

        <div className="pt-5">
          <ReadOnlyFieldGrid>
            <ReadOnlyField label="Nombre completo" value={perfil?.nombre_completo || "—"} />
            <ReadOnlyField label="Correo electrónico" value={perfil?.email || ""} />
            <ReadOnlyField label="Nombre de usuario" value={perfil?.username || ""} />
            <ReadOnlyField label="Cargo" value={perfil?.cargo_nombre || "—"} />
            <ReadOnlyField label="Rol" value={rolLabel(perfil?.rol)} />
          </ReadOnlyFieldGrid>
        </div>
      </div>

      <CollapsibleSection
        description="Actualiza tu nombre de usuario con tu contraseña actual."
        expanded={openSection === "username"}
        title="Cambiar nombre de usuario"
        onToggle={() => toggleSection("username")}
      >
        <ChangeUsernamePanel
          perfil={perfil}
          onCancel={() => setOpenSection(null)}
          onSaved={handleSectionSaved}
        />
      </CollapsibleSection>

      <CollapsibleSection
        description="Se enviará un código a tu correo al confirmar el cambio."
        expanded={openSection === "email"}
        title="Cambiar correo electrónico"
        onToggle={() => toggleSection("email")}
      >
        <ChangeEmailPanel
          perfil={perfil}
          onCancel={() => setOpenSection(null)}
          onSaved={handleSectionSaved}
        />
      </CollapsibleSection>

      <CollapsibleSection
        description="Se enviará un código a tu correo al confirmar el cambio."
        expanded={openSection === "password"}
        title="Cambiar contraseña"
        onToggle={() => toggleSection("password")}
      >
        <ChangePasswordPanel
          perfil={perfil}
          onCancel={() => setOpenSection(null)}
          onLogout={onLogout}
          onSaved={handleSectionSaved}
        />
      </CollapsibleSection>
    </div>
  );
}
