from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from rapidfuzz import fuzz
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from email_automation.config import Settings
from email_automation.models import ClientRequest, MatchCandidate, MatchStatus, SupplierOffer
from email_automation.schemas import DraftEmail, MatchEvaluation
from email_automation.services.openrouter import OpenRouterClient


MATCH_PROMPT = """
You evaluate whether a supplier offer matches a business client's computer hardware request.
Return strict JSON with:
- score: number from 0 to 100
- rationale: short explanation focused on fit, specs, quantity, and price
""".strip()

DRAFT_PROMPT = """
You write concise sales emails in Spanish for business clients.
Return strict JSON with:
- subject
- body

Rules:
- Write in Spanish.
- Be professional and direct.
- Mention the matched product and the key specs that matter.
- If some requested detail is missing, state it carefully.
- Close with a short call to action.
""".strip()


class MatchingService:
    def __init__(self, settings: Settings, openrouter: OpenRouterClient):
        self.settings = settings
        self.openrouter = openrouter

    async def find_matches_for_request(self, session: AsyncSession, request: ClientRequest) -> list[MatchCandidate]:
        offers = await session.scalars(self._active_offers_query())
        created_matches: list[MatchCandidate] = []

        for offer in offers:
            evaluation = await self.evaluate(request, offer)
            if evaluation.score < self.settings.match_threshold:
                continue
            draft = await self.generate_draft(request, offer, evaluation)
            match = MatchCandidate(
                client_request_id=request.id,
                supplier_offer_id=offer.id,
                score=evaluation.score,
                rationale=evaluation.rationale,
                draft_email_subject=draft.subject,
                draft_email_body=draft.body,
                status=MatchStatus.PROPOSED,
            )
            session.add(match)
            created_matches.append(match)
        await session.flush()
        return created_matches

    async def evaluate(self, request: ClientRequest, offer: SupplierOffer) -> MatchEvaluation:
        rule_score = self._rule_score(request, offer)
        llm_input = {
            "client_request": {
                "summary": request.summary,
                "request_kind": request.request_kind.value,
                "product_name": request.product_name,
                "use_case": request.use_case,
                "quantity_needed": request.quantity_needed,
                "budget_amount": request.budget_amount,
                "currency": request.currency,
                "required_specs": request.required_specs,
                "notes": request.notes,
            },
            "supplier_offer": {
                "product_name": offer.product_name,
                "brand": offer.brand,
                "model": offer.model,
                "quantity_available": offer.quantity_available,
                "unit_price": offer.unit_price,
                "currency": offer.currency,
                "specs": offer.specs,
                "notes": offer.notes,
            },
            "rule_score": rule_score,
        }
        evaluation = await self.openrouter.complete_json(
            system_prompt=MATCH_PROMPT,
            user_content=str(llm_input),
            response_model=MatchEvaluation,
        )
        evaluation.score = round((rule_score * 0.45) + (evaluation.score * 0.55), 2)
        return evaluation

    async def generate_draft(self, request: ClientRequest, offer: SupplierOffer, evaluation: MatchEvaluation) -> DraftEmail:
        payload = {
            "company_name": self.settings.company_name,
            "sales_signature": self.settings.sales_signature,
            "client_request": {
                "summary": request.summary,
                "product_name": request.product_name,
                "use_case": request.use_case,
                "quantity_needed": request.quantity_needed,
                "required_specs": request.required_specs,
            },
            "supplier_offer": {
                "product_name": offer.product_name,
                "brand": offer.brand,
                "model": offer.model,
                "quantity_available": offer.quantity_available,
                "unit_price": offer.unit_price,
                "currency": offer.currency,
                "specs": offer.specs,
                "notes": offer.notes,
            },
            "match_rationale": evaluation.rationale,
        }
        return await self.openrouter.complete_json(
            system_prompt=DRAFT_PROMPT,
            user_content=str(payload),
            response_model=DraftEmail,
        )

    def _rule_score(self, request: ClientRequest, offer: SupplierOffer) -> float:
        request_terms = " ".join(
            filter(
                None,
                [request.product_name, request.summary, request.use_case, self._flatten_dict(request.required_specs)],
            )
        )
        offer_terms = " ".join(
            filter(
                None,
                [offer.product_name, offer.brand, offer.model, offer.notes, self._flatten_dict(offer.specs)],
            )
        )
        text_score = fuzz.token_set_ratio(request_terms, offer_terms)

        quantity_score = 100.0
        if request.quantity_needed and offer.quantity_available:
            quantity_score = min(100.0, (offer.quantity_available / request.quantity_needed) * 100.0)

        budget_score = 100.0
        if request.budget_amount and offer.unit_price and request.currency == offer.currency:
            budget_score = 100.0 if offer.unit_price <= request.budget_amount else max(0.0, 100.0 - ((offer.unit_price - request.budget_amount) / request.budget_amount) * 100.0)

        return round((text_score * 0.6) + (quantity_score * 0.2) + (budget_score * 0.2), 2)

    def _flatten_dict(self, values: dict[str, Any] | None) -> str:
        if not values:
            return ""
        return " ".join(f"{key} {value}" for key, value in values.items())

    def _active_offers_query(self) -> Select[tuple[SupplierOffer]]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.supplier_offer_ttl_days)
        return (
            select(SupplierOffer)
            .options(selectinload(SupplierOffer.email))
            .where((SupplierOffer.valid_until.is_(None)) | (SupplierOffer.valid_until >= cutoff))
        )
