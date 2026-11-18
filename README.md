# bahazar

Jogo web multiplayer de economia, coleção e negociação de skins inspirado no Counter-Strike 2. Dinheiro e itens são **virtuais**: não há dinheiro real, depósito, saque nem itens reais da Steam.

Começa como jogo privado para um grupo de amigos (salas privadas, cada sala com economia própria). A arquitetura prepara, sem implementar agora, salas públicas, comunidades, rankings globais e temporadas.

## Estado
**Fase de arquitetura.** Ainda não há código de aplicação. A documentação para revisão está em [`project/`](project/INDEX.md).

## Stack (proposta, aguardando aprovação)
- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui (hospedagem: Vercel).
- Backend próprio: Python, Django e Django REST framework, PostgreSQL. Sem BaaS.

## Documentos
Comece por [`project/INDEX.md`](project/INDEX.md).

## Licença
[GNU AGPL-3.0](LICENSE). Quem hospedar uma versão modificada como serviço de rede deve oferecer o código-fonte aos usuários.

Este projeto é independente e **não é afiliado à Valve**. Counter-Strike e os nomes e imagens de skins pertencem aos seus donos; este repositório não distribui imagens deles.
