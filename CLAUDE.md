# offer_bot — Contexto para o Claude Code

> Este arquivo é lido automaticamente pelo Claude Code ao abrir o projeto.
> Mantenha-o atualizado conforme decisões mudam. Concisão > completude.

## O que é este projeto

Pipeline Python que automatiza publicação de ofertas com link de afiliado
em múltiplos canais: **Telegram, Instagram (feed + story), WhatsApp**, com
uma **bio page estática** servida via GitHub Pages que substitui Linktree.

Nicho inicial: **maternidade** (configurável via `NICHE` env var). Foco:
validar com **R$ 0 de custo** rodando em GitHub Actions.

Stack: Python 3.12, asyncio, httpx, Pillow, Anthropic SDK. Sem framework.

## Arquitetura

Pipeline linear orquestrado em `src/orchestrator.py`:

```
fetch -> dedupe -> filter+rank -> [generate -> review -> publish] -> bio page flush
```

Cada etapa é módulo independente, contrato único via `src/models.py`
(`Offer`, `ContentPiece`, `PublishResult`).

```
src/
├── models.py              # contratos — único acoplamento entre módulos
├── config.py              # settings via env
├── orchestrator.py        # pipeline principal
├── fetchers/              # 1 arquivo por fonte de ofertas
├── generators/            # transformação oferta -> conteúdo
├── reviewers/             # aprovação antes de publicar
├── publishers/            # 1 arquivo por canal de saída
└── storage/               # histórico/dedup
```

Padrão: Strategy + Open/Closed. **Adicionar fonte/canal novo = criar
arquivo novo. Não altere o orchestrator.**

## Decisões importantes (não revisitar sem motivo)

1. **NÃO usar bibliotecas não-oficiais** que simulam app mobile do
   Instagram ou WhatsApp (instagrapi, whatsapp-web.js, Selenium em
   conta logada). Ban garantido. Só APIs oficiais.

2. **Story do Instagram NÃO terá sticker de link clicável.** A Graph API
   oficial não suporta. Em vez disso, o Story aponta visualmente pra
   "LINK NA BIO" (CTA + seta pra cima). A bio do Instagram aponta pro
   GitHub Pages, que é atualizado automaticamente a cada run.

3. **Bio page é stateful, não per-offer.** O publisher `BioPagePublisher`
   é diferente dos outros: mantém as últimas N ofertas em `pages/offers.json`,
   regenera `pages/index.html`, e o GitHub Actions faz deploy via
   `actions/deploy-pages`. Único caso onde o pipeline desvia do padrão
   "per ContentPiece".

4. **WhatsApp usa Cloud API oficial em modo "group"** — bot precisa ser
   membro/admin do grupo. Cloud API tem janela de 24h pra mensagens não
   templated; pra grupo onde o bot é membro, isso não se aplica. Se quiser
   broadcast frio, exige template aprovado pela Meta (não implementado).

5. **Custo zero é restrição firme.** Hospedagem: GitHub Actions (2000
   min/mês free). LLM: Claude Haiku (~US$1/M tokens input). Imagens:
   Pillow local, zero IA generativa. Banco: JSON commitado no repo.
   Não introduzir VPS/DB/serviços pagos sem justificar.

6. **Claude API é usada SOMENTE para geração de copy.** Tudo mais é código
   determinístico. Não adicionar chamadas LLM em fetcher, reviewer ou
   publisher sem motivo claro — multiplica custo sem ganho.

## TODOs prioritários (em ordem)

1. ~~`fetchers/promobit.py::_parse`~~ — **feito.** Promobit não tem RSS
   público (SPA em Next.js); o fetcher raspa o HTML da página de categoria
   (`bs4` + `lxml`) e resolve o link de saída seguindo `/Redirect/to/<id>/`,
   que é um redirect client-side em JS (não HTTP) — a URL final é extraída
   via regex do `<script>` inline. Validado ao vivo contra `bebes-e-criancas`.

2. ~~`fetchers/promobit.py::_retag`~~ — **feito**, já existia e continua
   igual. Confirmado que sobrescreve corretamente o `tag=` que o próprio
   Promobit injeta nos links de saída da Amazon (não duplica parâmetro).

3. **Validar fluxo só com Telegram primeiro.** Em `orchestrator.py::build_per_piece_publishers`,
   comentar `InstagramPublisher` e `WhatsAppPublisher`. Rodar local com
   `.env` e canal de teste. Quando ver post chegar no Telegram com link
   afiliado certo, passar pros próximos.

4. **Token longo do Instagram Graph API.** Documento `docs/SETUP_META.md`
   (criar) com o passo-a-passo: criar app no Meta for Developers, vincular
   conta IG Business a uma Page, trocar token curto por longo (60 dias),
   gerenciar renovação. É o passo mais chato do projeto.

5. **WhatsApp Cloud API setup.** Verificar número, gerar token permanente
   (System User token), descobrir `group_id` do grupo onde o bot vai postar.

6. **Refinar imagens do Story.** O layout atual usa fonte DejaVu (fallback
   universal). Baixar Inter ou Poppins em `assets/fonts/` e atualizar
   `FONT_BOLD`/`FONT_REG` em `src/generators/story_image.py`.

7. **Implementar reviewer LLM** (`src/reviewers/llm.py`) se as regras
   determinísticas em `rules.py` ficarem curtas. Só adicionar quando houver
   sinal real de copy ruim passando.

## TODOs não-prioritários

- Migrar `history.json` -> SQLite quando passar de ~5k ofertas armazenadas.
- Adicionar mais fetchers (Pelando RSS, Shopee Open Platform API, Amazon
  PA-API depois das primeiras 3 vendas).
- Métricas: parsing dos painéis de afiliado pra fechar o loop e ranquear
  ofertas que historicamente convertem.

## Como rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher
python -m src.orchestrator
```

Pra gerar previews visuais sem chamar API:
```bash
python preview.py     # gera Story PNG + bio page HTML em ./data/generated e ./pages
```

## Deploy (GitHub Actions)

1. Push do repo.
2. **Settings → Pages → Source: GitHub Actions** (uma vez).
3. **Settings → Secrets and variables → Actions** — adicionar todos os
   `secrets.*` referenciados em `.github/workflows/run.yml` e a variável
   `vars.BRAND_HANDLE`.
4. Action roda automaticamente a cada hora (cron `0 * * * *`).
5. Bio page disponível em `https://<user>.github.io/<repo>/` — esse URL
   vai na bio do Instagram.

## Coisas que o Claude Code deve evitar

- **Não criar Web framework** (FastAPI/Flask). Não há servidor; é batch job.
- **Não adicionar Docker** antes de validar nicho. Overhead sem retorno.
- **Não criar testes unitários antes de o pipeline rodar end-to-end uma vez.**
  Testa com `preview.py` e com runs reais em canal de teste; quando estabilizar,
  adicionar testes nos contratos (`models.py`) e nos reviewers (regras).
- **Não fazer abstrações genéricas** ("PublisherFactory", "PipelineStage")
  até ter 3+ casos concretos. Hoje temos 4 publishers; mais abstração só
  atrapalha.
- **Não logar credenciais.** O `config.py` falha rápido se faltar var;
  nunca printar `Settings` inteiro.

## Convenções

- Async em todos os I/O (httpx async, gather pra paralelizar).
- Type hints obrigatórios.
- Logs estruturados via `logging` padrão; nada de print.
- Strings de usuário em pt-BR; código/comentários em inglês.
- Cada publisher é tolerante a falhas: retorna `PublishResult(success=False)`
  em vez de raise. Uma falha não pode parar a pipeline.

## Restrições legais

- **CDC e CONAR exigem disclaimer de publicidade/link afiliado.** O
  `TemplateCaptionGenerator` (`src/generators/template_caption.py`) usa
  a hashtag discreta `#publi` no fim da legenda — decisão explícita do
  usuário em 2026-07-08 de deixar mais discreto que "Publicidade | Link
  de afiliado", mas sem remover completamente.
- **Reviewer rejeita claims terapêuticos** ("cura", "milagre", "100% garantido"
  — ver `src/reviewers/rules.py::FORBIDDEN_CLAIMS`).
- LGPD: a única coleta é histórico interno; sem cadastro de usuários.

## Arquivos especialmente sensíveis

- `src/models.py` — mudança aqui quebra todos os módulos. Discutir antes.
- `.github/workflows/run.yml` — quebra silenciosa = bot para de rodar sem
  aviso. Testar via `workflow_dispatch` antes de commitar.
- `src/config.py` — adicionar var nova exige atualizar `.env.example` E
  o workflow.
