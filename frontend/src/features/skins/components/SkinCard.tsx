import { AtribuicaoSkinport } from "../../../components/AtribuicaoSkinport";
import { formatUsd } from "../../../lib/money";
import type { CatalogSkin } from "../../../types/api";

/** Cores de fundo por raridade (Consumer=cinza, Industrial=azul-claro, Mil-Spec=azul,
 * Restricted=roxo, Classified=rosa, Covert=vermelho, Contraband=laranja). */
const RARIDADE_CORES: Record<string, string> = {
  "Consumer Grade": "bg-neutral-500",
  "Industrial Grade": "bg-sky-400",
  "Mil-Spec Grade": "bg-blue-500",
  Restricted: "bg-purple-500",
  Classified: "bg-pink-500",
  Covert: "bg-red-500",
  Contraband: "bg-orange-500",
};

/** Iniciais das armas para o placeholder (ex.: "AK-47" → "AK", "M4A4" → "MA"). */
function inicialArma(weapon: string): string {
  // Extrai as duas primeiras letras do nome da arma (ignorando números e símbolos)
  const letras = weapon.match(/[A-Za-z]/g) ?? [];
  return letras.slice(0, 2).join("").toUpperCase();
}

interface SkinCardProps {
  skin: CatalogSkin;
}

export function SkinCard({ skin }: SkinCardProps) {
  const cor = RARIDADE_CORES[skin.rarity] ?? "bg-neutral-500";
  const inicial = inicialArma(skin.weapon);

  return (
    <li className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      <div
        role="img"
        className={`${cor} rounded-md aspect-square flex items-center justify-center text-white text-2xl font-bold select-none`}
        aria-label={`Placeholder da skin ${skin.name} (raridade: ${skin.rarity})`}
      >
        {inicial}
      </div>
      <span className="font-semibold text-sm truncate">{skin.name}</span>
      <span className="text-xs text-muted-foreground">{skin.weapon}</span>
      <span className="text-xs font-medium capitalize">{skin.rarity.toLowerCase()}</span>
      <span className="text-sm font-semibold">{formatUsd(skin.reference_price)}</span>
      {skin.collection && (
        <span className="text-xs text-muted-foreground truncate">{skin.collection}</span>
      )}
      <AtribuicaoSkinport />
    </li>
  );
}