from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Enum as SqlEnum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EmailCategory(str, Enum):
    SUPPLIER = "supplier"
    CLIENT = "client"
    IRRELEVANT = "irrelevant"


class RequestKind(str, Enum):
    SPECIFIC_PRODUCT = "specific_product"
    USE_CASE = "use_case"


class MatchStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    NO_MATCH = "no_match"
    SENT = "sent"


class EmailMessage(Base):
    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(255), index=True)
    internet_message_id: Mapped[str | None] = mapped_column(String(512))
    sender_name: Mapped[str | None] = mapped_column(String(255))
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(500))
    body_text: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    category: Mapped[EmailCategory] = mapped_column(SqlEnum(EmailCategory), index=True)
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    classification_reasoning: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    attachments: Mapped[list[EmailAttachment]] = relationship(back_populates="email", cascade="all, delete-orphan")
    supplier_offers: Mapped[list[SupplierOffer]] = relationship(back_populates="email", cascade="all, delete-orphan")
    client_requests: Mapped[list[ClientRequest]] = relationship(back_populates="email", cascade="all, delete-orphan")


class EmailAttachment(Base):
    __tablename__ = "email_attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    email: Mapped[EmailMessage] = relationship(back_populates="attachments")


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id", ondelete="CASCADE"), index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255))
    supplier_email: Mapped[str] = mapped_column(String(255), index=True)
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    brand: Mapped[str | None] = mapped_column(String(255), index=True)
    model: Mapped[str | None] = mapped_column(String(255), index=True)
    quantity_available: Mapped[int | None] = mapped_column(Integer)
    unit_price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(16))
    specs: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    email: Mapped[EmailMessage] = relationship(back_populates="supplier_offers")
    matches: Mapped[list[MatchCandidate]] = relationship(back_populates="supplier_offer")


class ClientRequest(Base):
    __tablename__ = "client_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id", ondelete="CASCADE"), index=True)
    client_name: Mapped[str | None] = mapped_column(String(255))
    client_email: Mapped[str] = mapped_column(String(255), index=True)
    summary: Mapped[str] = mapped_column(Text)
    request_kind: Mapped[RequestKind] = mapped_column(SqlEnum(RequestKind), index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), index=True)
    use_case: Mapped[str | None] = mapped_column(Text)
    quantity_needed: Mapped[int | None] = mapped_column(Integer)
    budget_amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(16))
    required_specs: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    email: Mapped[EmailMessage] = relationship(back_populates="client_requests")
    matches: Mapped[list[MatchCandidate]] = relationship(back_populates="client_request", cascade="all, delete-orphan")


class MatchCandidate(Base):
    __tablename__ = "match_candidates"
    __table_args__ = (UniqueConstraint("client_request_id", "supplier_offer_id", name="uq_client_supplier_match"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    client_request_id: Mapped[int] = mapped_column(ForeignKey("client_requests.id", ondelete="CASCADE"), index=True)
    supplier_offer_id: Mapped[int] = mapped_column(ForeignKey("supplier_offers.id", ondelete="CASCADE"), index=True)
    score: Mapped[float] = mapped_column(Float, index=True)
    rationale: Mapped[str] = mapped_column(Text)
    draft_email_subject: Mapped[str | None] = mapped_column(String(255))
    draft_email_body: Mapped[str | None] = mapped_column(Text)
    status: Mapped[MatchStatus] = mapped_column(SqlEnum(MatchStatus), default=MatchStatus.PROPOSED, index=True)
    telegram_message_id: Mapped[int | None] = mapped_column(Integer)
    human_feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    client_request: Mapped[ClientRequest] = relationship(back_populates="matches")
    supplier_offer: Mapped[SupplierOffer] = relationship(back_populates="matches")
