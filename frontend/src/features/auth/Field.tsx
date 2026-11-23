interface FieldProps {
  id: string;
  label: string;
  value: string;
  onChange: (valor: string) => void;
  type?: "text" | "email" | "password" | "number";
  autoComplete?: string;
  hint?: string;
  error?: string;
}

/** Campo de formulário acessível: rótulo ligado ao input, erro anunciado e marcado como inválido. */
export function Field({
  id,
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  hint,
  error,
}: FieldProps) {
  const descricoes = [hint ? `${id}-dica` : null, error ? `${id}-erro` : null]
    .filter(Boolean)
    .join(" ");

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(evento) => onChange(evento.target.value)}
        autoComplete={autoComplete}
        required
        aria-invalid={error ? true : undefined}
        aria-describedby={descricoes || undefined}
        className="h-10 rounded-md border border-border bg-secondary px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {hint && (
        <p id={`${id}-dica`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-erro`} className="text-sm text-primary">
          {error}
        </p>
      )}
    </div>
  );
}
