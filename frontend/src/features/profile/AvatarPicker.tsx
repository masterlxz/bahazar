import { AVATAR_COR as COR } from "../../components/ui/avatar";
import { cn } from "../../lib/utils";
import { AVATAR_KEYS, type AvatarKey } from "../../types/api";

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
