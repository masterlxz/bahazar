import { useState } from "react";

import { Button } from "./button";

interface ConfirmButtonProps {
  /** Verbo da ação ("Remover"). Com `name`, forma o nome acessível: "Remover carla_03". */
  label: string;
  name: string;
  onConfirm: () => void;
  disabled?: boolean;
}

/**
 * Botão de ação difícil de desfazer: o 1º clique só pede confirmação; a ação sai no 2º.
 * Sem `window.confirm` (bloqueia a página e é ruim de testar) e sem modal.
 */
export function ConfirmButton({ label, name, onConfirm, disabled }: ConfirmButtonProps) {
  const [confirmando, setConfirmando] = useState(false);

  if (!confirmando) {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled={disabled}
        aria-label={`${label} ${name}`}
        onClick={() => {
          setConfirmando(true);
          onConfirm();
        }}
      >
        {label}
      </Button>
    );
  }

  return (
    <span className="flex gap-2">
      <Button
        size="sm"
        disabled={disabled}
        aria-label={`Confirmar ${label} ${name}`}
        onClick={() => {
          setConfirmando(false);
          onConfirm();
        }}
      >
        Confirmar?
      </Button>
      <Button
        variant="ghost"
        size="sm"
        aria-label={`Cancelar ${label} ${name}`}
        onClick={() => setConfirmando(false)}
      >
        Cancelar
      </Button>
    </span>
  );
}
