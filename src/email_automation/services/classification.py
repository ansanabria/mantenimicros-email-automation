from __future__ import annotations

from email_automation.schemas import ClassificationResult, EmailEnvelope
from email_automation.services.openrouter import OpenRouterClient


CLASSIFICATION_PROMPT = """
You classify incoming inbox messages for a company that buys and sells computers for business customers.

Return strict JSON with these fields:
- category: one of supplier, client, irrelevant
- confidence: number between 0 and 1
- reasoning: short explanation
- supplier_offers: array of offers extracted from the email and attachments
- client_requests: array of client needs extracted from the email and attachments
- irrelevant_reason: null or short explanation

Rules:
- Supplier emails usually contain product lists, inventory, prices, stock, spec sheets, quotes, or attached spreadsheets/PDFs.
- Client emails usually ask for specific products or describe a business need that hardware should solve.
- Irrelevant means spam, newsletters, unrelated promotions, or content unrelated to business computer sales.
- Use attachment content as part of the classification.
- If the email contains several products or several client asks, return multiple entries.
- Keep extracted specs and notes concise but useful.
""".strip()


class ClassificationService:
    def __init__(self, openrouter: OpenRouterClient):
        self.openrouter = openrouter

    async def classify(self, message: EmailEnvelope) -> ClassificationResult:
        attachment_text = []
        for attachment in message.attachments:
            attachment_text.append(
                {
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "size_bytes": attachment.size_bytes,
                    "extracted_text": attachment.extracted_text,
                }
            )

        payload = {
            "sender_name": message.sender_name,
            "sender_email": message.sender_email,
            "subject": message.subject,
            "body_text": message.body_text,
            "attachments": attachment_text,
        }
        result = await self.openrouter.complete_json(
            system_prompt=CLASSIFICATION_PROMPT,
            user_content=str(payload),
            response_model=ClassificationResult,
        )
        return result
