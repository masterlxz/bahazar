import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Backend Django em desenvolvimento. O proxy faz o navegador enxergar UMA origem só
// (localhost:5173): sem isso o cookie de sessão não seria enviado ao backend.
// (Valor fixo: ler variável de ambiente aqui exigiria @types/node; fica para quando precisar.)
const BACKEND = "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": { target: BACKEND },
      "/_allauth": { target: BACKEND },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
