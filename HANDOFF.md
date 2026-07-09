# HANDOFF — Primeira mensagem pro Claude Code

Cole isso no Claude Code logo após `claude` na raiz do repo.

---

Oi Claude. Esse projeto foi rascunhado em outra sessão e agora estou
trazendo pra você terminar.

**Antes de qualquer coisa, lê o `CLAUDE.md` da raiz** — tem todo o
contexto: arquitetura, decisões já tomadas (que não quero revisitar),
TODOs em ordem de prioridade, e as armadilhas das plataformas
(Instagram/WhatsApp) que descobrimos.

O esqueleto está pronto e roda. O que falta:

## Tarefa 1 (bloqueante, faz primeiro)

Implementar `src/fetchers/promobit.py::_parse` usando `feedparser`. O
método recebe XML do RSS do Promobit e o `Niche`, e devolve `list[Offer]`.
Campos a extrair de cada `<item>`: título, preço atual, preço antigo (se
houver), URL do produto, URL da imagem. Calcular `discount_pct` a partir
dos preços. Usar `_make_id` (já implementado) pra gerar o ID. Chamar
`_retag` no URL antes de instanciar o Offer (pra trocar o tag de afiliado
pelo nosso).

Pra `_retag`: detectar se a URL é Shopee (`*.shopee.com.br`) ou Amazon
(`*.amazon.com.br` ou `amzn.to`), e injetar/substituir o parâmetro de
afiliado (`af_id` na Shopee, `tag` na Amazon). URLs de outras lojas
devolve sem mexer.

Quando terminar essas duas funções, rode `python preview.py` pra
confirmar que nada quebrou. Depois rode `python -m src.orchestrator`
com um `.env` mínimo (só Telegram preenchido) e os outros publishers
comentados em `orchestrator.py::build_per_piece_publishers`, mirando
num canal de teste do Telegram que eu vou criar.

## Tarefa 2

Quando a Tarefa 1 estiver verde no Telegram, criar `docs/SETUP_META.md`
com o passo-a-passo pra configurar o Instagram Graph API (criar app no
Meta for Developers, vincular conta IG Business a uma Page do Facebook,
gerar token de longa duração de 60 dias, lidar com renovação). Isso é
chato e quero documentar pra não esquecer.

## Estilo

- Não invente requisitos novos. Se aparecer ambiguidade, pergunta.
- Não refatora código que está funcionando. O `CLAUDE.md` diz onde NÃO
  abstrair.
- Pequenos commits, mensagens em pt-BR.
- Antes de instalar dependência nova, justifica.

Vai.
