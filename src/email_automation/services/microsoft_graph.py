from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import msal

from email_automation.config import Settings
from email_automation.schemas import AttachmentDocument, EmailEnvelope


class MicrosoftGraphClient:
    APP_SCOPES = ["https://graph.microsoft.com/.default"]
    USER_SCOPES = ["Mail.ReadWrite", "Mail.Send"]
    UNREAD_LOOKBACK_DAYS = 7

    def __init__(self, settings: Settings):
        self.settings = settings
        self.auth_mode = settings.microsoft_auth_mode
        self._token_cache: msal.SerializableTokenCache | None = None

        if self.auth_mode == "delegated":
            if not settings.microsoft_client_id:
                raise RuntimeError(
                    "MICROSOFT_CLIENT_ID is required for delegated Microsoft auth"
                )
            authority_tenant = settings.microsoft_tenant_id or "consumers"
            authority = f"https://login.microsoftonline.com/{authority_tenant}"
            self._token_cache = msal.SerializableTokenCache()
            if settings.microsoft_token_cache_path.exists():
                self._token_cache.deserialize(
                    settings.microsoft_token_cache_path.read_text(encoding="utf-8")
                )
            self.app = msal.PublicClientApplication(
                settings.microsoft_client_id,
                authority=authority,
                token_cache=self._token_cache,
            )
            return

        if not all(
            [
                settings.microsoft_tenant_id,
                settings.microsoft_client_id,
                settings.microsoft_client_secret,
                settings.microsoft_mailbox,
            ]
        ):
            raise RuntimeError("Microsoft 365 credentials are not fully configured")
        authority = f"https://login.microsoftonline.com/{settings.microsoft_tenant_id}"
        self.app = msal.ConfidentialClientApplication(
            settings.microsoft_client_id,
            authority=authority,
            client_credential=settings.microsoft_client_secret,
        )

    def authenticate_interactive(self) -> None:
        self._token(interactive=True)

    def _token(self, interactive: bool = False) -> str:
        if self.auth_mode == "delegated":
            return self._delegated_token(interactive=interactive)

        result = self.app.acquire_token_for_client(scopes=self.APP_SCOPES)
        token = result.get("access_token")
        if not token:
            raise RuntimeError(f"Unable to acquire Microsoft Graph token: {result}")
        return token

    def _delegated_token(self, interactive: bool) -> str:
        result: dict[str, Any] | None = None
        accounts = self.app.get_accounts()
        if accounts:
            result = self.app.acquire_token_silent(
                self.USER_SCOPES, account=accounts[0]
            )
            token = (result or {}).get("access_token")
            if token:
                self._persist_token_cache()
                return token

        if not interactive:
            description = (result or {}).get("error_description")
            message = (
                "No cached Microsoft Graph user token is available. Run "
                "`uv run email-automation-auth` and complete the device-code sign-in "
                "for the Outlook account before starting the workflow."
            )
            if description:
                message = f"{message} Last token error: {description}"
            raise RuntimeError(message)

        flow = self.app.initiate_device_flow(scopes=self.USER_SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Unable to start Microsoft device flow: {flow}")

        print(
            flow.get("message") or "Open https://microsoft.com/devicelogin and sign in."
        )
        result = self.app.acquire_token_by_device_flow(flow)
        token = result.get("access_token")
        if not token:
            raise RuntimeError(
                "Unable to acquire delegated Microsoft Graph token: "
                f"{result.get('error_description') or result}"
            )
        self._persist_token_cache()
        return token

    def _persist_token_cache(self) -> None:
        if not self._token_cache or not self._token_cache.has_state_changed:
            return
        self.settings.microsoft_token_cache_path.write_text(
            self._token_cache.serialize(), encoding="utf-8"
        )

    async def list_inbox_messages(self, limit: int = 20) -> list[EmailEnvelope]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.UNREAD_LOOKBACK_DAYS))
        cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        params = {
            "$top": str(limit),
            "$orderby": "receivedDateTime asc",
            "$select": "id,conversationId,internetMessageId,subject,body,from,receivedDateTime,hasAttachments,isRead",
            "$filter": f"isRead eq false and receivedDateTime ge {cutoff_iso}",
        }
        data = await self._request(
            "GET", self._mailbox_path("/mailFolders/Inbox/messages"), params=params
        )
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
                    sender_name=(
                        (item.get("from") or {}).get("emailAddress") or {}
                    ).get("name"),
                    sender_email=(
                        (item.get("from") or {}).get("emailAddress") or {}
                    ).get("address", "unknown@example.com"),
                    subject=item.get("subject") or "(no subject)",
                    body_text=self._strip_html(
                        (item.get("body") or {}).get("content") or ""
                    ),
                    received_at=datetime.fromisoformat(
                        item["receivedDateTime"].replace("Z", "+00:00")
                    ),
                    is_read=item.get("isRead", False),
                    attachments=attachments,
                    raw_payload=item,
                )
            )
        return envelopes

    async def mark_message_read(self, message_id: str) -> None:
        await self._request(
            "PATCH",
            self._mailbox_path(f"/messages/{message_id}"),
            json={"isRead": True},
        )

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
        data = await self._request(
            "GET", self._mailbox_path(f"/messages/{message_id}/attachments")
        )
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
        async with httpx.AsyncClient(
            base_url=self.settings.microsoft_graph_base_url, timeout=120.0
        ) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}

    def _mailbox_path(self, suffix: str) -> str:
        if self.auth_mode == "delegated":
            return f"/me{suffix}"
        return f"/users/{self.settings.microsoft_mailbox}{suffix}"

    def _strip_html(self, html: str) -> str:
        text = re.sub(r"<br\\s*/?>", "\n", html)
        text = re.sub(r"</p>", "\n", text)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
