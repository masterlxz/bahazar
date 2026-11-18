import { useMutation, useQueryClient } from "@tanstack/react-query";

import { updateAvatar } from "../../services/me";
import AvatarPicker from "./AvatarPicker";
import { ME_KEY, useMe } from "./useMe";

export default function ProfilePage() {
  const queryClient = useQueryClient();
  const me = useMe();
  const trocarAvatar = useMutation({
    mutationFn: updateAvatar,
    onSuccess: (atualizado) => queryClient.setQueryData(ME_KEY, atualizado),
  });

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 px-4 py-12">
      <h1 className="text-2xl font-bold tracking-tight">Seu perfil</h1>

      {me.isError && (
        <p role="alert" className="text-sm text-primary">
          Não foi possível carregar o perfil. Tente novamente.
        </p>
      )}

      {me.data && (
        <>
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg border border-border bg-card p-6 text-sm">
            <dt className="text-muted-foreground">Usuário</dt>
            <dd>{me.data.username}</dd>
            <dt className="text-muted-foreground">E-mail</dt>
            <dd>{me.data.email}</dd>
          </dl>

          <section className="flex flex-col gap-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Avatar
            </h2>
            <AvatarPicker
              atual={me.data.avatar}
              inicial={me.data.username}
              disabled={trocarAvatar.isPending}
              onChange={(chave) => trocarAvatar.mutate(chave)}
            />
            {trocarAvatar.isError && (
              <p role="alert" className="text-sm text-primary">
                Não foi possível trocar o avatar. Tente novamente.
              </p>
            )}
          </section>
        </>
      )}
    </main>
  );
}
