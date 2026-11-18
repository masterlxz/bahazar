// Classes completas e estáticas: o Tailwind só gera o que enxerga literalmente no código.
const RARIDADES = [
  { nome: "Consumer", classe: "bg-rarity-consumer" },
  { nome: "Industrial", classe: "bg-rarity-industrial" },
  { nome: "Mil-Spec", classe: "bg-rarity-milspec" },
  { nome: "Restricted", classe: "bg-rarity-restricted" },
  { nome: "Classified", classe: "bg-rarity-classified" },
  { nome: "Covert", classe: "bg-rarity-covert" },
  { nome: "Contraband", classe: "bg-rarity-contraband" },
] as const;

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <header className="flex flex-col gap-2">
        <h1 className="text-4xl font-bold tracking-tight">bahazar</h1>
        <p className="text-muted-foreground">
          Economia, coleção e negociação de skins. Em construção.
        </p>
      </header>

      <section className="flex flex-col gap-3 rounded-lg border border-border bg-card p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Raridades
        </h2>
        <ul className="flex flex-wrap gap-2">
          {RARIDADES.map(({ nome, classe }) => (
            <li
              key={nome}
              data-testid="rarity-chip"
              className="flex items-center gap-2 rounded-full border border-border px-3 py-1 text-sm"
            >
              <span className={`size-2.5 rounded-full ${classe}`} aria-hidden="true" />
              {nome}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
