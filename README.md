# bahazar

Jogo web multiplayer de economia, coleção e negociação de skins inspirado no Counter-Strike 2. Dinheiro e itens são **virtuais**: não há dinheiro real, depósito, saque nem itens reais da Steam.

Começa como jogo privado para um grupo de amigos (salas privadas, cada sala com economia própria). A arquitetura prepara, sem implementar agora, salas públicas, comunidades, rankings globais e temporadas.

## Estado
**Etapa 1 (fundação) quase concluída:** backend Django com autenticação (cadastro, login, perfil) e frontend com as telas de entrar, cadastrar e perfil. Ainda **não há jogo** (salas, skins, mercado): isso começa na Etapa 2. O plano e as decisões estão em [`project/`](project/INDEX.md).

## Stack
- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui (hospedagem prevista: Vercel).
- Backend próprio: Python, Django e Django REST framework, PostgreSQL, django-allauth (autenticação). Sem BaaS.

## Rodar em desenvolvimento
O frontend e o backend precisam rodar juntos: o Vite repassa `/api` e `/_allauth` para o Django (`localhost:8000`), e assim o navegador enxerga uma origem só (necessário para o cookie de sessão).

**Backend** (precisa de Python 3.13 e PostgreSQL local):
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DB_NAME=bahazar DB_USER=bahazar DB_PASSWORD=...  # um banco PostgreSQL vazio
python manage.py migrate
python manage.py runserver                              # http://localhost:8000
```
Em dev os e-mails (confirmação, redefinição de senha) saem no console do `runserver`.

**Frontend** (Node 24 ou mais novo):
```bash
cd frontend
npm install
npm run dev                                             # http://localhost:5173
```
Abra `http://localhost:5173`, cadastre-se, entre, troque o avatar e saia.

Testes e verificação de tipos rodam **só no GitHub (CI)**; o build é feito só no PC do dono, à mão (ADR 0017 do workspace). Na VM de desenvolvimento do agente nada disso roda.

## Documentos
Comece por [`project/INDEX.md`](project/INDEX.md).

## Licença
[GNU AGPL-3.0](LICENSE). Quem hospedar uma versão modificada como serviço de rede deve oferecer o código-fonte aos usuários.

Este projeto é independente e **não é afiliado à Valve**. Counter-Strike e os nomes e imagens de skins pertencem aos seus donos; este repositório não distribui imagens deles.
