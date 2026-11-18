import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router";

import { Button } from "../../components/ui/button";
import { signup } from "../../services/auth";
import { ApiError } from "../../services/http";
import { Field } from "./Field";
import { MSG } from "./messages";
import { SESSION_KEY } from "./useSession";

export default function SignupPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<Record<string, string[]>>({});
  const [erroGeral, setErroGeral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErros({});
    setErroGeral(null);
    setEnviando(true);
    try {
      await signup({ username: username.trim(), email: email.trim(), password: senha });
      await queryClient.invalidateQueries({ queryKey: SESSION_KEY });
      navigate("/perfil");
    } catch (e) {
      if (e instanceof ApiError && e.status === 400) {
        setErros(e.fieldErrors);
        setErroGeral(e.nonFieldErrors[0] ?? null);
      } else {
        setErroGeral(MSG.erroGenerico);
      }
      setEnviando(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-sm flex-col gap-6 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Criar conta</h1>
      <form onSubmit={enviar} className="flex flex-col gap-4">
        <Field
          id="username"
          label="Nome de usuário"
          value={username}
          onChange={setUsername}
          autoComplete="username"
          hint={MSG.dicaUsername}
          error={erros.username?.[0]}
        />
        <Field
          id="email"
          label="E-mail"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
          error={erros.email?.[0]}
        />
        <Field
          id="senha"
          label="Senha"
          type="password"
          value={senha}
          onChange={setSenha}
          autoComplete="new-password"
          hint="Mínimo de 10 caracteres."
          error={erros.password?.[0]}
        />
        {erroGeral && (
          <p role="alert" className="text-sm text-primary">
            {erroGeral}
          </p>
        )}
        <Button type="submit" disabled={enviando}>
          Criar conta
        </Button>
      </form>
      <p className="text-sm text-muted-foreground">
        Já tem conta?{" "}
        <Link to="/entrar" className="text-foreground underline">
          Entrar
        </Link>
      </p>
    </main>
  );
}
