"""Shopee Affiliate Open API fetcher (GraphQL).

Ver memória de projeto "shopee-affiliate-api" para a doc completa levantada
com o time (endpoints, auth, rate limit). Resumo do que importa aqui:

- Endpoint único: https://open-api.affiliate.shopee.com.br/graphql, sempre
  POST, sempre 200 mesmo com erro — o erro vem em `errors[]` no corpo.
- Auth por assinatura, não OAuth: header
  `Authorization: SHA256 Credential={AppId}, Timestamp={ts}, Signature={sig}`
  onde `sig = SHA256(AppId + Timestamp + Payload + Secret)` e Payload é o
  body exato (string) que vai no POST — por isso assinamos a string já
  serializada, não o dict, pra garantir que bate byte a byte.
- Rate limit: 8000 req/h — folgado pro volume deste projeto, não precisa
  de backoff sofisticado ainda.
- `productOfferV2` é o endpoint usado aqui: já devolve `offerLink` com
  tracking de afiliado pronto (sem precisar de `_retag` manual como no
  Promobit — ver `promobit.py::_retag`).
- Vários campos de resposta (`price`, `appExistRate`, `appNewRate`,
  `webExistRate`, `webNewRate`) estão marcados "To Be Removed" na doc
  oficial — não usamos nenhum deles aqui, ficamos com `priceMin`/`priceMax`.

Credenciais (App ID + Secret) exigem aprovação manual da Shopee — enquanto
não tiver, `ShopeeFetcher` simplesmente não é instanciado pelo orchestrator
(ver `build_fetchers` em orchestrator.py). Ainda não testado contra a API
real (acesso solicitado, aprovação pendente em 2026-08-08) — validar com
`preview.py`/log real assim que a credencial chegar, antes de confiar no
parsing da resposta.
"""

import asyncio
import hashlib
import json
import logging
import time

import httpx

from ..models import Niche, Offer, Source
from .base import Fetcher

log = logging.getLogger(__name__)

GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Termos de busca por nicho — mesma ideia do NICHE_KEYWORDS do Promobit,
# mas aqui viram query de busca de verdade (productOfferV2 não tem
# "categoria de nicho", só keyword/productCatId). Só maternidade populado
# por ora (nicho inicial do projeto — ver CLAUDE.md).
NICHE_SEARCH_TERMS: dict[Niche, list[str]] = {
    Niche.MOTHERHOOD: [
        "fralda", "bebê", "carrinho de bebê", "berço",
        "mamadeira", "roupinha bebê",
    ],
}

_PRODUCT_OFFER_QUERY = """
query($keyword: String, $sortType: Int, $page: Int, $limit: Int) {
  productOfferV2(keyword: $keyword, sortType: $sortType, page: $page, limit: $limit) {
    nodes {
      itemId
      productName
      offerLink
      imageUrl
      priceMin
      priceMax
      priceDiscountRate
      commissionRate
      sales
      shopName
      periodStartTime
      periodEndTime
    }
    pageInfo {
      page
      limit
      hasNextPage
    }
  }
}
"""

# sortType: COMMISSION_DESC — prioriza comissão alta, já que é isso que
# torna a oferta valer a pena publicar (ver doc oficial productOfferV2).
_SORT_COMMISSION_DESC = 5


def _sign(app_id: str, secret: str, payload: str, timestamp: int) -> str:
    """SHA256(AppId + Timestamp + Payload + Secret), hex minúsculo.

    `payload` precisa ser exatamente a string enviada no corpo do POST —
    reaproveitar o mesmo texto pros dois (assinatura e request) em vez de
    serializar duas vezes, pra não arriscar um espaço em branco diferente
    quebrar a assinatura.
    """
    factor = f"{app_id}{timestamp}{payload}{secret}"
    return hashlib.sha256(factor.encode("utf-8")).hexdigest()


class ShopeeFetcher(Fetcher):
    name = "shopee"

    def __init__(self, app_id: str, secret: str, rate_limit_seconds: float = 0.5):
        self.app_id = app_id
        self.secret = secret
        self.rate_limit_seconds = rate_limit_seconds

    async def fetch(self, niche: Niche, limit: int = 50) -> list[Offer]:
        terms = NICHE_SEARCH_TERMS.get(niche)
        if not terms:
            return []

        offers: dict[int, Offer] = {}  # itemId -> Offer, dedupe entre termos

        async with httpx.AsyncClient(timeout=15) as client:
            for term in terms:
                if len(offers) >= limit:
                    break
                try:
                    nodes = await self._search(client, term, limit - len(offers))
                except Exception as e:
                    log.warning("Shopee search failed for %r: %s", term, e)
                    continue

                for node in nodes:
                    try:
                        offer = self._to_offer(node, niche)
                    except Exception as e:
                        # Um node malformado não pode derrubar o resto da
                        # página — cai fora só ele, os outros seguem.
                        log.warning("Shopee item %s unparseable, skipping: %s",
                                    node.get("itemId", "?"), e)
                        continue
                    if offer:
                        offers[node["itemId"]] = offer

                await asyncio.sleep(self.rate_limit_seconds)

        return list(offers.values())

    async def _search(self, client: httpx.AsyncClient, keyword: str, limit: int) -> list[dict]:
        variables = {
            "keyword": keyword,
            "sortType": _SORT_COMMISSION_DESC,
            "page": 1,
            "limit": min(limit, 50),
        }
        body = {"query": _PRODUCT_OFFER_QUERY, "variables": variables}
        # separators compactos e determinísticos — essa é a string exata
        # que vai no POST e que também alimenta a assinatura.
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        timestamp = int(time.time())
        signature = _sign(self.app_id, self.secret, payload, timestamp)
        headers = {
            "Content-Type": "application/json",
            "Authorization": (
                f"SHA256 Credential={self.app_id}, "
                f"Timestamp={timestamp}, Signature={signature}"
            ),
        }

        r = await client.post(GRAPHQL_URL, content=payload.encode("utf-8"), headers=headers)
        r.raise_for_status()
        data = r.json()

        errors = data.get("errors")
        if errors:
            for err in errors:
                code = err.get("extensions", {}).get("code")
                log.warning("Shopee API error %s for keyword %r: %s", code, keyword, err.get("message"))
            return []

        return data["data"]["productOfferV2"]["nodes"]

    def _to_offer(self, node: dict, niche: Niche) -> Offer | None:
        try:
            price_now = float(node["priceMin"])
        except (TypeError, ValueError):
            log.warning("Shopee item %s has no usable priceMin, skipping", node.get("itemId"))
            return None

        discount_pct = int(node.get("priceDiscountRate") or 0)
        # 0 < x < 100 guarda contra item sem desconto (0, sem price_was) e
        # contra o caso raro de 100% off (divisão por zero).
        price_was = (round(price_now / (1 - discount_pct / 100), 2)
                     if 0 < discount_pct < 100 else None)

        item_id = node["itemId"]
        return Offer(
            id=self._make_id(item_id, price_now),
            title=node["productName"],
            price_now=price_now,
            price_was=price_was,
            discount_pct=discount_pct,
            affiliate_url=node["offerLink"],
            image_url=node.get("imageUrl", ""),
            source=Source.SHOPEE,
            niche=niche,
        )

    @staticmethod
    def _make_id(item_id: int, price: float) -> str:
        return hashlib.sha1(f"{item_id}|{price}".encode()).hexdigest()[:16]
