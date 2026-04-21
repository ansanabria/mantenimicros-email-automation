from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from html import escape

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from email_automation.config import Settings, get_settings
from email_automation.db import AsyncSessionLocal, get_db, init_db
from email_automation.models import MatchCandidate, MatchStatus
from email_automation.schemas import DraftEmail
from email_automation.services.attachments import AttachmentService
from email_automation.services.classification import ClassificationService
from email_automation.services.intake import IntakeService
from email_automation.services.matching import MatchingService
from email_automation.services.microsoft_graph import MicrosoftGraphClient
from email_automation.services.openrouter import OpenRouterClient
from email_automation.services.telegram_bot import TelegramBotService

logger = logging.getLogger(__name__)


class AppContainer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.inbox_lock = asyncio.Lock()
        self.openrouter = OpenRouterClient(settings)
        self.attachments = AttachmentService(settings, openrouter=self.openrouter)
        self.classification = ClassificationService(self.openrouter)
        self.matching = MatchingService(settings, self.openrouter)
        self.telegram = TelegramBotService(settings)
        self.graph = MicrosoftGraphClient(settings)
        self.intake = IntakeService(
            graph=self.graph,
            attachments=self.attachments,
            classification=self.classification,
            matching=self.matching,
            telegram=self.telegram,
        )

    async def process_inbox(self, session: AsyncSession) -> dict[str, int]:
        async with self.inbox_lock:
            return await self.intake.process_inbox(session)


async def approve_match(
    match: MatchCandidate, session: AsyncSession, container: AppContainer
) -> None:
    if not match.client_request or not match.supplier_offer:
        raise HTTPException(status_code=404, detail="Match relations are not loaded")
    if not match.draft_email_subject or not match.draft_email_body:
        raise HTTPException(status_code=400, detail="Draft is empty")
    body_html = "<br>".join(
        escape(line) for line in match.draft_email_body.splitlines()
    )
    await container.graph.send_email(
        match.client_request.client_email, match.draft_email_subject, body_html
    )
    match.status = MatchStatus.SENT
    await session.commit()


async def revise_match(
    match: MatchCandidate,
    instructions: str,
    session: AsyncSession,
    container: AppContainer,
) -> None:
    if not match.client_request or not match.supplier_offer:
        raise HTTPException(status_code=404, detail="Match relations are not loaded")
    evaluation = await container.matching.evaluate(
        match.client_request, match.supplier_offer
    )
    draft = await container.openrouter.complete_json(
        system_prompt=(
            "Rewrite the Spanish draft email according to the user feedback. Return JSON with subject and body."
        ),
        user_content=str(
            {
                "current_subject": match.draft_email_subject,
                "current_body": match.draft_email_body,
                "feedback": instructions,
                "client_request": match.client_request.summary,
                "supplier_offer": match.supplier_offer.product_name,
                "match_rationale": evaluation.rationale,
            }
        ),
        response_model=DraftEmail,
    )
    match.draft_email_subject = draft.subject
    match.draft_email_body = draft.body
    match.human_feedback = instructions
    match.status = MatchStatus.PROPOSED
    await session.commit()
    await container.telegram.send_match_for_review(
        match, match.client_request, match.supplier_offer
    )


async def polling_loop(container: AppContainer) -> None:
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await container.process_inbox(session)
        except Exception:
            logger.exception("Inbox polling failed")
        await asyncio.sleep(container.settings.polling_interval_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await init_db()
    container = AppContainer(settings)
    app.state.container = container
    await container.telegram.ensure_webhook()
    poller = asyncio.create_task(polling_loop(container))
    try:
        yield
    finally:
        poller.cancel()
        with suppress(asyncio.CancelledError):
            await poller
        await container.openrouter.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Email Automation", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/internal/process-inbox")
    async def process_inbox(session: AsyncSession = Depends(get_db)) -> dict[str, int]:
        container: AppContainer = app.state.container
        return await container.process_inbox(session)

    @app.post("/telegram/webhook/{secret}")
    async def telegram_webhook(
        secret: str, payload: dict, session: AsyncSession = Depends(get_db)
    ) -> dict[str, bool]:
        container: AppContainer = app.state.container
        if secret != container.settings.telegram_webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
        await container.telegram.process_update(
            payload,
            session,
            on_approve=lambda match, db_session: approve_match(
                match, db_session, container
            ),
            on_revise=lambda match, instructions, db_session: revise_match(
                match, instructions, db_session, container
            ),
        )
        return {"ok": True}

    return app
