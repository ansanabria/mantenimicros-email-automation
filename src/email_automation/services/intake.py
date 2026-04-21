from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from email_automation.models import (
    ClientRequest,
    EmailAttachment,
    EmailMessage,
    SupplierOffer,
)
from email_automation.schemas import (
    ClassificationResult,
    ClientRequestDraft,
    EmailEnvelope,
    SupplierOfferDraft,
)
from email_automation.services.attachments import AttachmentService
from email_automation.services.classification import ClassificationService
from email_automation.services.matching import MatchingService
from email_automation.services.microsoft_graph import MicrosoftGraphClient
from email_automation.services.telegram_bot import TelegramBotService


class IntakeService:
    def __init__(
        self,
        graph: MicrosoftGraphClient,
        attachments: AttachmentService,
        classification: ClassificationService,
        matching: MatchingService,
        telegram: TelegramBotService,
    ):
        self.graph = graph
        self.attachments = attachments
        self.classification = classification
        self.matching = matching
        self.telegram = telegram

    async def process_inbox(self, session: AsyncSession) -> dict[str, int]:
        processed = 0
        skipped = 0
        messages = await self.graph.list_inbox_messages()
        for message in messages:
            existing_email = await session.scalar(
                select(EmailMessage).where(
                    EmailMessage.external_id == message.external_id
                )
            )
            if existing_email:
                if not existing_email.is_read:
                    await self._mark_email_as_read(message.external_id, existing_email, session)
                skipped += 1
                continue
            try:
                email = await self.process_message(message, session)
                await session.commit()
                await self._mark_email_as_read(message.external_id, email, session)
            except IntegrityError:
                await session.rollback()
                skipped += 1
                continue
            processed += 1
        return {"processed": processed, "skipped": skipped}

    async def process_message(
        self, message: EmailEnvelope, session: AsyncSession
    ) -> EmailMessage:
        message.attachments = await self.attachments.process(message.attachments)
        classification = await self.classification.classify(message)
        email = await self._save_email(message, classification, session)
        if classification.category.value == "supplier":
            await self._save_supplier_offers(email, classification.supplier_offers, session)
            existing_requests = (
                await session.scalars(select(ClientRequest).order_by(ClientRequest.id.asc()))
            ).all()
            for request in existing_requests:
                matches = await self.matching.find_matches_for_request(session, request)
                await self._notify_matches(session, request, matches)
        elif classification.category.value == "client":
            requests = await self._save_client_requests(
                email, classification.client_requests, session
            )
            for request in requests:
                matches = await self.matching.find_matches_for_request(session, request)
                if not matches:
                    await self.telegram.send_no_match_alert(request)
                    continue
                await self._notify_matches(session, request, matches)
        return email

    async def _notify_matches(
        self,
        session: AsyncSession,
        request: ClientRequest,
        matches: list,
    ) -> None:
        if not matches:
            return
        await session.flush()
        loaded_request = await session.scalar(
            select(ClientRequest)
            .options(selectinload(ClientRequest.matches))
            .where(ClientRequest.id == request.id)
        )
        for match in matches:
            offer = await session.get(SupplierOffer, match.supplier_offer_id)
            if not offer or not loaded_request:
                continue
            match.telegram_message_id = await self.telegram.send_match_for_review(
                match, loaded_request, offer
            )

    async def _save_email(
        self,
        message: EmailEnvelope,
        classification: ClassificationResult,
        session: AsyncSession,
    ) -> EmailMessage:
        email = EmailMessage(
            external_id=message.external_id,
            conversation_id=message.conversation_id,
            internet_message_id=message.internet_message_id,
            sender_name=message.sender_name,
            sender_email=message.sender_email,
            subject=message.subject,
            body_text=message.body_text,
            received_at=message.received_at,
            is_read=message.is_read,
            category=classification.category,
            classification_confidence=classification.confidence,
            classification_reasoning=classification.reasoning,
            raw_payload=message.raw_payload,
        )
        session.add(email)
        await session.flush()

        for attachment in message.attachments:
            session.add(
                EmailAttachment(
                    email_id=email.id,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size_bytes=attachment.size_bytes,
                    storage_path=attachment.storage_path,
                    extracted_text=attachment.extracted_text,
                    metadata_json=attachment.metadata,
                )
            )
        await session.flush()
        return email

    async def _save_supplier_offers(
        self,
        email: EmailMessage,
        offers: list[SupplierOfferDraft],
        session: AsyncSession,
    ) -> None:
        for offer in offers:
            session.add(
                SupplierOffer(
                    email_id=email.id,
                    supplier_name=email.sender_name,
                    supplier_email=email.sender_email,
                    product_name=offer.product_name,
                    brand=offer.brand,
                    model=offer.model,
                    quantity_available=offer.quantity_available,
                    unit_price=offer.unit_price,
                    currency=offer.currency,
                    specs=offer.specs,
                    notes=offer.notes,
                    source_excerpt=offer.source_excerpt,
                )
            )
        await session.flush()

    async def _save_client_requests(
        self,
        email: EmailMessage,
        requests: list[ClientRequestDraft],
        session: AsyncSession,
    ) -> list[ClientRequest]:
        created: list[ClientRequest] = []
        for request in requests:
            entity = ClientRequest(
                email_id=email.id,
                client_name=email.sender_name,
                client_email=email.sender_email,
                summary=request.summary,
                request_kind=request.request_kind,
                product_name=request.product_name,
                use_case=request.use_case,
                quantity_needed=request.quantity_needed,
                budget_amount=request.budget_amount,
                currency=request.currency,
                required_specs=request.required_specs,
                notes=request.notes,
            )
            session.add(entity)
            created.append(entity)
        await session.flush()
        return created

    async def _mark_email_as_read(
        self,
        external_id: str,
        email: EmailMessage,
        session: AsyncSession,
    ) -> None:
        if email.is_read:
            return
        await self.graph.mark_message_read(external_id)
        email.is_read = True
        email.read_at = datetime.now(timezone.utc)
        await session.commit()
