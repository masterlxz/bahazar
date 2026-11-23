import { cn } from "../../lib/utils";
import type { AvatarKey } from "../../types/api";

// Classes completas e estáticas (o Tailwind só gera o que enxerga literalmente no código).
// Cores provisórias: os desenhos reais ficam para a etapa visual.
export const AVATAR_COR: Record<AvatarKey, string> = {
  default: "bg-secondary",
  ember: "bg-orange-500",
  glacier: "bg-sky-400",
  verdant: "bg-green-500",
  violet: "bg-violet-500",
  amber: "bg-amber-400",
  slate: "bg-slate-500",
  crimson: "bg-red-700",
};

interface AvatarProps {
  avatar: AvatarKey;
  /** Nome do jogador: a inicial vai dentro do círculo. */
  username: string;
  className?: string;
}

/** Círculo colorido com a inicial. Decorativo: o nome do jogador aparece em texto ao lado. */
export function Avatar({ avatar, username, className }: AvatarProps) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "flex size-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold uppercase text-white",
        AVATAR_COR[avatar],
        className,
      )}
    >
      {username.charAt(0)}
    </span>
  );
}
