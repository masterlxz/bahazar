/** Atribuição do preço de referência (ADR 0015, ponto 4): uma vez por tela que mostra preço. */
export function AtribuicaoSkinport() {
  return (
    <p className="text-xs text-muted-foreground">
      Preço de referência via{" "}
      <a
        href="https://skinport.com"
        target="_blank"
        rel="noopener"
        className="underline"
      >
        Skinport
      </a>
    </p>
  );
}
