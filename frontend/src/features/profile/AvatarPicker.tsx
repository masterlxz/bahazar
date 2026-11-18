import { cn } from "../../lib/utils";
import { AVATAR_KEYS, type AvatarKey } from "../../types/api";

// Classes completas e estáticas (o Tailwind só gera o que enxerga literalmente no código).
// Cores provisórias: os desenhos reais ficam para a etapa visual.
const COR: Record<AvatarKey, string> = {
  default: "bg-secondary",
  ember: "bg-orange-500",
  glacier: "bg-sky-400",
  verdant: "bg-green-500",
  violet: "bg-violet-500",
  amber: "bg-amber-400",
  slate: "bg-slate-500",
  crimson: "bg-red-700",
};

interface AvatarPickerProps {
  atual: AvatarKey;
  inicial: string;
  onChange: (chave: AvatarKey) => void;
  disabled?: boolean;
}

export default function AvatarPicker({ atual, inicial, onChange, disabled }: AvatarPickerProps) {
  return (
    <div role="radiogroup" aria-label="Avatar" className="flex flex-wrap gap-3">
      {AVATAR_KEYS.map((chave) => (
        <button
          key={chave}
          type="button"
          role="radio"
          aria-checked={chave === atual}
          aria-label={`Avatar ${chave}`}
          disabled={disabled}
          onClick={() => onChange(chave)}
          className={cn(
            "flex size-12 items-center justify-center rounded-full text-lg font-semibold uppercase text-white ring-offset-2 ring-offset-background transition disabled:opacity-60",
            COR[chave],
            chave === atual && "ring-2 ring-primary",
          )}
        >
          {inicial.charAt(0)}
        </button>
      ))}
    </div>
  );
}
