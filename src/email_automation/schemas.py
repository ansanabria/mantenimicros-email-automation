from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from email_automation.models import EmailCategory, MatchStatus, RequestKind


class AttachmentDocument(BaseModel):
    filename: str
    content_type: str | None = None
    size_bytes: int = 0
    content_bytes: bytes = b""
    extracted_text: str | None = None
    storage_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EmailEnvelope(BaseModel):
    external_id: str
    conversation_id: str | None = None
    internet_message_id: str | None = None
    sender_name: str | None = None
    sender_email: str
    subject: str
    body_text: str
    received_at: datetime
    is_read: bool = False
    attachments: list[AttachmentDocument] = Field(default_factory=list)
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class SupplierOfferDraft(BaseModel):
    product_name: str
    brand: str | None = None
    model: str | None = None
    quantity_available: int | None = None
    unit_price: float | None = None
    currency: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    source_excerpt: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_string_offer(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"product_name": value, "source_excerpt": value}
        return value


class ClientRequestDraft(BaseModel):
    summary: str
    request_kind: RequestKind
    product_name: str | None = None
    use_case: str | None = None
    quantity_needed: int | None = None
    budget_amount: float | None = None
    currency: str | None = None
    required_specs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_string_request(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {
                "summary": value,
                "request_kind": RequestKind.USE_CASE,
                "use_case": value,
            }
        return value


class ClassificationResult(BaseModel):
    category: EmailCategory
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    supplier_offers: list[SupplierOfferDraft] = Field(default_factory=list)
    client_requests: list[ClientRequestDraft] = Field(default_factory=list)
    irrelevant_reason: str | None = None


class MatchEvaluation(BaseModel):
    score: float = Field(ge=0.0, le=100.0)
    rationale: str


class DraftEmail(BaseModel):
    subject: str
    body: str


class TelegramActionResult(BaseModel):
    handled: bool
    message: str | None = None


class MatchNotification(BaseModel):
    match_id: int
    status: MatchStatus
    telegram_message_id: int | None = None
