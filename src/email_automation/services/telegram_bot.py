from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from email_automation.config import Settings
from email_automation.models import ClientRequest, MatchCandidate, MatchStatus, SupplierOffer
from email_automation.schemas import TelegramActionResult


class TelegramBotService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def ensure_webhook(self) -> None:
        if not (self.settings.telegram_bot_token and self.settings.telegram_webhook_url):
            return
        await self._request(
            "setWebhook",
            {
                "url": f"{self.settings.telegram_webhook_url}/telegram/webhook/{self.settings.telegram_webhook_secret}",
                "allowed_updates": ["callback_query", "message"],
            },
        )

    async def send_match_for_review(self, match: MatchCandidate, request: ClientRequest, offer: SupplierOffer) -> int | None:
        if not self.settings.telegram_chat_id:
            return None
        text = (
            f"Nueva coincidencia #{match.id}\n"
            f"Cliente: {request.client_name or request.client_email}\n"
            f"Solicitud: {request.summary}\n"
            f"Oferta: {offer.product_name} {offer.brand or ''} {offer.model or ''}\n"
            f"Precio: {offer.unit_price or 'N/D'} {offer.currency or ''}\n"
            f"Score: {match.score}\n\n"
            f"Asunto sugerido: {match.draft_email_subject}\n\n"
            f"{match.draft_email_body}"
        ).strip()
        payload = {
            "chat_id": self.settings.telegram_chat_id,
            "text": text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "Aprobar", "callback_data": f"approve:{match.id}"},
                        {"text": "Rechazar", "callback_data": f"reject:{match.id}"},
                    ],
                    [{"text": "Pedir ajuste", "callback_data": f"revise:{match.id}"}],
                ]
            },
        }
        response = await self._request("sendMessage", payload)
        return ((response.get("result") or {}).get("message_id"))

    async def send_no_match_alert(self, request: ClientRequest) -> None:
        if not self.settings.telegram_chat_id:
            return
        text = (
            f"Sin stock para solicitud #{request.id}\n"
            f"Cliente: {request.client_name or request.client_email}\n"
            f"Detalle: {request.summary}"
        )
        await self._request("sendMessage", {"chat_id": self.settings.telegram_chat_id, "text": text})

    async def process_update(self, update: dict[str, Any], session: AsyncSession, on_approve: Any, on_revise: Any) -> TelegramActionResult:
        callback = update.get("callback_query")
        if callback:
            await self._answer_callback(callback["id"])
            action, _, raw_match_id = (callback.get("data") or "").partition(":")
            if not raw_match_id.isdigit():
                return TelegramActionResult(handled=False, message="Invalid callback payload")
            match_id = int(raw_match_id)
            match = await self._load_match(session, match_id)
            if not match:
                return TelegramActionResult(handled=False, message="Match not found")
            if action == "approve":
                await on_approve(match, session)
                return TelegramActionResult(handled=True, message=f"Approved match {match_id}")
            if action == "reject":
                match.status = MatchStatus.REJECTED
                await session.commit()
                return TelegramActionResult(handled=True, message=f"Rejected match {match_id}")
            if action == "revise":
                match.status = MatchStatus.REVISION_REQUESTED
                await session.commit()
                await self._request(
                    "sendMessage",
                    {
                        "chat_id": self.settings.telegram_chat_id,
                        "text": f"Usa /revise {match_id} <instrucciones> para ajustar el borrador.",
                    },
                )
                return TelegramActionResult(handled=True, message=f"Revision requested for match {match_id}")

        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        if text.startswith("/revise "):
            parts = text.split(maxsplit=2)
            if len(parts) < 3 or not parts[1].isdigit():
                return TelegramActionResult(handled=False, message="Usage: /revise <match_id> <instructions>")
            match = await self._load_match(session, int(parts[1]))
            if not match:
                return TelegramActionResult(handled=False, message="Match not found")
            await on_revise(match, parts[2], session)
            return TelegramActionResult(handled=True, message=f"Revised match {match.id}")

        return TelegramActionResult(handled=False, message="Update ignored")

    async def _load_match(self, session: AsyncSession, match_id: int) -> MatchCandidate | None:
        result = await session.scalar(
            select(MatchCandidate)
            .options(
                selectinload(MatchCandidate.client_request),
                selectinload(MatchCandidate.supplier_offer),
            )
            .where(MatchCandidate.id == match_id)
        )
        return result

    async def _answer_callback(self, callback_id: str) -> None:
        await self._request("answerCallbackQuery", {"callback_query_id": callback_id})

    async def _request(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required for Telegram actions")
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/{method}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
