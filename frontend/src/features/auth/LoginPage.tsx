import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";

import { Button } from "../../components/ui/button";
import { login } from "../../services/auth";
import { ApiError } from "../../services/http";
import { Field } from "./Field";
import { MSG } from "./messages";
import { SESSION_KEY } from "./useSession";

export default function LoginPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [identificador, setIdentificador] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro(null);
    setEnviando(true);
    try {
      await login(identificador.trim(), senha);
      await queryClient.invalidateQueries({ queryKey: SESSION_KEY });
      navigate("/perfil");
    } catch (e) {
      setErro(e instanceof ApiError && e.status === 400 ? MSG.loginInvalido : MSG.erroGenerico);
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-sm flex-col gap-6 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Entrar</h1>
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <Field
          id="identificador"
          label="Usuário ou e-mail"
          value={identificador}
          onChange={setIdentificador}
          autoComplete="username"
        />
        <Field
          id="senha"
          label="Senha"
          type="password"
          value={senha}
          onChange={setSenha}
          autoComplete="current-password"
        />
        {erro && (
          <p role="alert" className="text-sm text-primary">
            {erro}
          </p>
        )}
        <Button type="submit" disabled={enviando}>
          Entrar
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        Ainda não tem conta?{" "}
        <Link to="/cadastrar" className="text-foreground underline">
          Cadastre-se
        </Link>
      </p>
    </main>
  );
}
