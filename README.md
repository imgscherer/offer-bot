# offer_bot

Pipeline modular para curar e publicar ofertas em múltiplos canais
(Telegram, Instagram, WhatsApp), com link de afiliado.

## Arquitetura

```
fetch → dedupe → filter → generate → review → publish
```

Cada etapa é um módulo independente. Adicionar uma nova fonte ou um
novo canal de publicação = criar um arquivo novo. Zero alteração no
orchestrator (Strategy + open/closed).

```
src/
├── models.py          # Contratos (Offer, ContentPiece, PublishResult)
├── config.py          # Settings via env
├── orchestrator.py    # Pipeline principal
│
├── fetchers/          # Coleta de ofertas (1 arquivo por fonte)
│   ├── base.py        # interface Fetcher
│   └── promobit.py    # exemplo (RSS gratuito)
│
├── generators/        # Transformação oferta → conteúdo
│   ├── caption.py     # copy via Claude API
│   └── story_image.py # imagem 1080x1920 via Pillow
│
├── reviewers/         # Aprovação antes de publicar
│   └── rules.py       # regras determinísticas (rápido, grátis)
│
├── publishers/        # Distribuição (1 arquivo por canal)
│   ├── base.py        # interface Publisher
│   ├── telegram.py    # Bot API (grátis, ilimitado)
│   ├── instagram.py   # Meta Graph API
│   └── whatsapp.py    # Meta Cloud API
│
└── storage/
    └── history.py     # dedup + log de publicações (JSON)
```

## Setup local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher
python -m src.orchestrator
```

## Deploy gratuito

GitHub Actions agendado de hora em hora. Cadastre os secrets em
**Settings → Secrets and variables → Actions** com os mesmos nomes
do `.env.example`. Histórico persistido via commit no próprio repo.

Limite do free tier: 2.000 min/mês. Cada run leva ~1-2 min, então
24×30 = 720 runs/mês = ~720 min usados. Folga grande.

## Próximos passos (ordem sugerida)

1. **Implementar `PromobitFetcher._parse`** usando `feedparser`.
2. **Subir só o Telegram** primeiro (mais barato/rápido pra validar).
3. **Adicionar Instagram** depois que tiver fluxo no Telegram rodando.
4. **WhatsApp por último** — Cloud API tem mais burocracia.
5. **Trocar JSON por SQLite** quando histórico passar de ~5k entradas.
6. **Adicionar reviewer LLM** se regras determinísticas ficarem curtas.

## Não fazer

- Selenium/Playwright/whatsapp-web.js → ban garantido nas plataformas.
- Postar 50 ofertas/hora → spam, mata o engajamento.
- Reutilizar a mesma copy → use Claude pra variar tom por nicho/canal.
