import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from email_automation.config import Settings
from email_automation.models import (
    Base,
    ClientRequest,
    EmailCategory,
    EmailMessage,
    MatchCandidate,
    RequestKind,
    SupplierOffer,
)
from email_automation.schemas import (
    ClassificationResult,
    ClientRequestDraft,
    EmailEnvelope,
    SupplierOfferDraft,
)
from email_automation.services.intake import IntakeService
from email_automation.services.matching import MatchingService
from email_automation.services.microsoft_graph import MicrosoftGraphClient
from email_automation.services.openrouter import OpenRouterClient


class DummyOpenRouter(OpenRouterClient):
    async def complete_json(self, system_prompt, user_content, response_model):
        if response_model.__name__ == "MatchEvaluation":
            return response_model(score=80, rationale="Good fit")
        return response_model(subject="Propuesta de equipos", body="Tenemos una opcion disponible.")


def test_rule_score_rewards_similar_products():
    service = MatchingService(Settings(), DummyOpenRouter(Settings()))
    request = ClientRequest(
        id=1,
        email_id=1,
        client_email="client@example.com",
        summary="Necesito 10 laptops Lenovo ThinkPad con 16GB RAM",
        request_kind=RequestKind.SPECIFIC_PRODUCT,
        product_name="Lenovo ThinkPad",
        quantity_needed=10,
        required_specs={"ram": "16GB"},
    )
    offer = SupplierOffer(
        id=1,
        email_id=1,
        supplier_email="supplier@example.com",
        product_name="Lenovo ThinkPad T14",
        brand="Lenovo",
        model="T14",
        quantity_available=12,
        unit_price=900,
        currency="USD",
        specs={"ram": "16GB", "storage": "512GB SSD"},
    )

    assert service._rule_score(request, offer) >= 70


class DummyGraph:
    def __init__(self, batches):
        self.batches = list(batches)
        self.marked_read_ids = []

    async def list_inbox_messages(self):
        return self.batches.pop(0) if self.batches else []

    async def mark_message_read(self, message_id):
        self.marked_read_ids.append(message_id)


class CaptureGraphClient(MicrosoftGraphClient):
    def __init__(self, settings):
        super().__init__(settings)
        self.last_params = None

    async def _request(self, method, path, **kwargs):
        self.last_params = kwargs.get("params")
        return {"value": []}


class DummyAttachments:
    async def process(self, attachments):
        return list(attachments)


class DummyClassification:
    async def classify(self, message):
        if message.subject == "supplier":
            return ClassificationResult(
                category=EmailCategory.SUPPLIER,
                confidence=1,
                reasoning="supplier",
                supplier_offers=[
                    SupplierOfferDraft(
                        product_name="Lenovo ThinkPad",
                        brand="Lenovo",
                        model="T14",
                    )
                ],
                client_requests=[],
            )
        return ClassificationResult(
            category=EmailCategory.CLIENT,
            confidence=1,
            reasoning="client",
            supplier_offers=[],
            client_requests=[
                ClientRequestDraft(
                    summary="Need Lenovo ThinkPad laptops",
                    request_kind=RequestKind.SPECIFIC_PRODUCT,
                    product_name="Lenovo ThinkPad",
                )
            ],
        )


class DummyTelegram:
    def __init__(self):
        self.no_match_alerts = 0
        self.review_messages = 0

    async def send_no_match_alert(self, request):
        self.no_match_alerts += 1

    async def send_match_for_review(self, match, request, offer):
        self.review_messages += 1
        return 123


def _message(message_id: str, subject: str, sender: str) -> EmailEnvelope:
    return EmailEnvelope(
        external_id=message_id,
        sender_email=sender,
        sender_name=sender,
        subject=subject,
        body_text=subject,
        received_at=datetime.now(timezone.utc),
        is_read=False,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("order", [("supplier", "client"), ("client", "supplier")])
async def test_intake_creates_match_regardless_of_email_order(order):
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    telegram = DummyTelegram()
    intake = IntakeService(
        graph=DummyGraph(
            [
                [_message("1", order[0], f"{order[0]}@example.com")],
                [_message("2", order[1], f"{order[1]}@example.com")],
            ]
        ),
        attachments=DummyAttachments(),
        classification=DummyClassification(),
        matching=MatchingService(Settings(), DummyOpenRouter(Settings())),
        telegram=telegram,
    )

    async with session_maker() as session:
        await intake.process_inbox(session)
        await intake.process_inbox(session)
        match_count = await session.scalar(select(func.count()).select_from(MatchCandidate))

    await engine.dispose()

    assert match_count == 1
    assert telegram.review_messages == 1


@pytest.mark.anyio
async def test_intake_marks_processed_email_as_read_in_db_and_graph():
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    graph = DummyGraph([[_message("1", "client", "client@example.com")]])
    intake = IntakeService(
        graph=graph,
        attachments=DummyAttachments(),
        classification=DummyClassification(),
        matching=MatchingService(Settings(), DummyOpenRouter(Settings())),
        telegram=DummyTelegram(),
    )

    async with session_maker() as session:
        await intake.process_inbox(session)
        email = await session.scalar(
            select(EmailMessage).where(EmailMessage.external_id == "1")
        )

    await engine.dispose()

    assert graph.marked_read_ids == ["1"]
    assert email is not None
    assert email.is_read is True
    assert email.read_at is not None


@pytest.mark.anyio
async def test_graph_only_queries_unread_messages_from_last_seven_days():
    settings = Settings(
        microsoft_auth_mode="delegated",
        microsoft_client_id="test-client-id",
    )
    client = CaptureGraphClient(settings)

    await client.list_inbox_messages()

    assert client.last_params is not None
    assert client.last_params["$filter"].startswith(
        "isRead eq false and receivedDateTime ge "
    )


@pytest.mark.anyio
async def test_matching_excludes_stale_offers_without_valid_until():
    db_path = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(supplier_offer_ttl_days=30)
    service = MatchingService(settings, DummyOpenRouter(settings))

    async with session_maker() as session:
        session.add_all(
            [
                SupplierOffer(
                    email_id=1,
                    supplier_email="old@example.com",
                    product_name="Old ThinkPad",
                    created_at=datetime.now(timezone.utc) - timedelta(days=45),
                ),
                SupplierOffer(
                    email_id=1,
                    supplier_email="new@example.com",
                    product_name="New ThinkPad",
                    created_at=datetime.now(timezone.utc) - timedelta(days=5),
                ),
                SupplierOffer(
                    email_id=1,
                    supplier_email="explicit@example.com",
                    product_name="Explicit ThinkPad",
                    valid_until=datetime.now(timezone.utc) + timedelta(days=5),
                    created_at=datetime.now(timezone.utc) - timedelta(days=90),
                ),
            ]
        )
        await session.commit()
        offers = (await session.scalars(service._active_offers_query())).all()

    await engine.dispose()

    assert {offer.product_name for offer in offers} == {
        "New ThinkPad",
        "Explicit ThinkPad",
    }
