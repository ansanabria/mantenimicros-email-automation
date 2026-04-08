from __future__ import annotations

import base64
import re
from datetime import datetime
from typing import Any

import httpx
import msal

from email_automation.config import Settings
from email_automation.schemas import AttachmentDocument, EmailEnvelope


class MicrosoftGraphClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not all([
            settings.microsoft_tenant_id,
            settings.microsoft_client_id,
            settings.microsoft_client_secret,
            settings.microsoft_mailbox,
        ]):
            raise RuntimeError("Microsoft 365 credentials are not fully configured")
        authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"
        self.app = msal.ConfidentialClientApplication(
            settings.microsoft_client_id,
            authority=authority,
            client_credential=settings.microsoft_client_secret,
        )

    def _token(self) -> str:
        result = self.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        token = result.get("access_token")
        if not token:
            raise RuntimeError(f"Unable to acquire Microsoft Graph token: {result}")
        return token

    async def list_inbox_messages(self, limit: int = 20) -> list[EmailEnvelope]:
        params = {
            "$top": str(limit),
            "$orderby": "receivedDateTime asc",
            "$select": "id,conversationId,internetMessageId,subject,body,from,receivedDateTime,hasAttachments",
            "$filter": "isRead eq false",
        }
        data = await self._request("GET", self._mailbox_path("/mailFolders/Inbox/messages"), params=params)
        envelopes: list[EmailEnvelope] = []
        for item in data.get("value", []):
            attachments: list[AttachmentDocument] = []
            if item.get("hasAttachments"):
                attachments = await self.get_attachments(item["id"])
            envelopes.append(
                EmailEnvelope(
                    external_id=item["id"],
                    conversation_id=item.get("conversationId"),
                    internet_message_id=item.get("internetMessageId"),
                    sender_name=((item.get("from") or {}).get("emailAddress") or {}).get("name"),
                    sender_email=((item.get("from") or {}).get("emailAddress") or {}).get("address", "unknown@example.com"),
                    subject=item.get("subject") or "(no subject)",
                    body_text=self._strip_html((item.get("body") or {}).get("content") or ""),
                    received_at=datetime.fromisoformat(item["receivedDateTime"].replace("Z", "+00:00")),
                    attachments=attachments,
                    raw_payload=item,
                )
            )
        return envelopes

    async def send_email(self, recipient: str, subject: str, body_html: str) -> None:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body_html},
                "toRecipients": [{"emailAddress": {"address": recipient}}],
            },
            "saveToSentItems": True,
        }
        await self._request("POST", self._mailbox_path("/sendMail"), json=payload)

    async def get_attachments(self, message_id: str) -> list[AttachmentDocument]:
        data = await self._request("GET", self._mailbox_path(f"/messages/{message_id}/attachments"))
        attachments: list[AttachmentDocument] = []
        for item in data.get("value", []):
            content_bytes = base64.b64decode(item.get("contentBytes") or b"")
            attachments.append(
                AttachmentDocument(
                    filename=item.get("name") or "attachment",
                    content_type=item.get("contentType"),
                    size_bytes=item.get("size") or len(content_bytes),
                    content_bytes=content_bytes,
                    metadata={"graph_attachment_id": item.get("id")},
                )
            )
        return attachments

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._token()}"
        async with httpx.AsyncClient(base_url=self.settings.microsoft_graph_base_url, timeout=120.0) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}

    def _mailbox_path(self, suffix: str) -> str:
        return f"/users/{self.settings.microsoft_mailbox}{suffix}"

    def _strip_html(self, html: str) -> str:
        text = re.sub(r"<br\\s*/?>", "\n", html)
        text = re.sub(r"</p>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
