import { FormField, formInputClass } from "./AdminControls";

export default function ReadOnlyField({ label, value }) {
  return (
    <FormField label={label}>
      <input className={`${formInputClass} bg-app-fondo`} disabled readOnly value={value || ""} />
    </FormField>
  );
}

export function ReadOnlyFieldGrid({ children }) {
  return <div className="grid gap-4 sm:grid-cols-2">{children}</div>;
}
