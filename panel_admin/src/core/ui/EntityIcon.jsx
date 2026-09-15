import { layout } from "../typography";

export default function EntityIcon({ children, className = "" }) {
  return (
    <span className={`${layout.entityIcon} ${className}`} aria-hidden="true">
      {children}
    </span>
  );
}
