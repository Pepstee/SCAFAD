/**
 * Lightweight assignee picker.  Phase 2 ships with a hard-coded user list
 * (matches `users.KNOWN_USERS` on the backend); Phase 5 swaps the data
 * source.
 */

interface AssigneePickerProps {
  value: string | null;
  onChange: (value: string | null) => void;
  disabled?: boolean;
}

const ASSIGNEE_OPTIONS: Array<{ id: string; label: string }> = [
  { id: "", label: "Unassigned" },
  { id: "analyst@scafad.local", label: "Primary Analyst" },
  { id: "analyst-2@scafad.local", label: "Secondary Analyst" },
];

export function AssigneePicker({ value, onChange, disabled = false }: AssigneePickerProps) {
  return (
    <select
      data-testid="assignee-picker"
      aria-label="Assignee"
      value={value ?? ""}
      disabled={disabled}
      onChange={(e) => {
        const raw = e.target.value;
        onChange(raw === "" ? null : raw);
      }}
      className="rounded border border-surface-border bg-surface-subtle px-2 py-1 text-xs text-ink focus:border-ink-accent focus:outline-none"
    >
      {ASSIGNEE_OPTIONS.map((opt) => (
        <option key={opt.id || "unassigned"} value={opt.id}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
