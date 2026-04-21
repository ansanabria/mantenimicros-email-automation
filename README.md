# Email Automation

Python backend for classifying inbound supplier/client emails, storing structured data, matching client requests against supplier offers, and routing draft replies through Telegram for human approval.

## Current architecture

- `FastAPI` app for Railway deployment
- `Microsoft 365 / Graph API` inbox polling and outbound sending
- `PydanticAI` managing structured LLM workflows on top of OpenRouter
- `SQLite` persistence for messages, attachments, offers, requests, and matches
- `Telegram Bot API` webhook for approvals, rejections, and draft revision requests
- `uv` project layout and dependency management

## Implemented first pass

- Poll unread inbox messages from a Microsoft 365 mailbox
- Parse PDF, Excel, CSV, TXT, and image attachments
- Classify each email as supplier, client, or irrelevant using PydanticAI + OpenRouter
- Persist email metadata, extracted attachment text, supplier offers, and client requests
- Score supplier/client matches with rules plus LLM evaluation
- Draft a Spanish reply and send it to Telegram with inline approval buttons
- Send the approved email back through Microsoft 365

## Environment variables

Create a `.env` file with at least:

```env
MICROSOFT_AUTH_MODE=application
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
MICROSOFT_TENANT_ID=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_MAILBOX=
MICROSOFT_TOKEN_CACHE_PATH=data/msal_token_cache.json
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
TELEGRAM_WEBHOOK_SECRET=change-me
TELEGRAM_WEBHOOK_URL=https://your-app.up.railway.app
BASE_URL=https://your-app.up.railway.app
```

Optional settings:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/email_automation.db
ATTACHMENT_STORAGE_PATH=data/attachments
POLLING_INTERVAL_SECONDS=60
MATCH_THRESHOLD=65
SUPPLIER_OFFER_TTL_DAYS=30
COMPANY_NAME=Your Company
SALES_SIGNATURE=Equipo Comercial
```

## Run locally

```bash
uv sync
uv run email-automation-auth  # only for MICROSOFT_AUTH_MODE=delegated
uv run email-automation
```

### Personal Outlook (`@outlook.com`) setup

- Set `MICROSOFT_AUTH_MODE=delegated`
- Set `MICROSOFT_TENANT_ID=consumers`
- Set `MICROSOFT_CLIENT_ID` to a public-client app registration that allows personal Microsoft accounts
- Leave `MICROSOFT_CLIENT_SECRET` empty
- The app uses `/me/...` Graph endpoints in delegated mode, so `MICROSOFT_MAILBOX` is not required
- Run `uv run email-automation-auth` once in a terminal and complete the device-code sign-in flow
- Keep `MICROSOFT_TOKEN_CACHE_PATH` on persistent storage if you deploy the app remotely

## Railway deployment

- `Dockerfile` builds the app with `uv` and starts FastAPI with `uvicorn`
- `railway.toml` configures Dockerfile-based deploys and the `/health` check
- Mount a persistent volume if you want durable `SQLite` and attachment storage

Manual processing endpoint:

```bash
curl -X POST http://localhost:8000/internal/process-inbox
```

## Telegram review flow

- `Aprobar`: sends the drafted email to the client through Microsoft 365
- `Rechazar`: discards the proposal
- `Pedir ajuste`: marks the match for revision
- `/revise <match_id> <instructions>`: rewrites the draft with your extra instructions

## Railway notes

- Attachments are stored on local disk, so use a Railway volume if you need persistence across deploys.
- SQLite also needs a volume for durable production storage. If you outgrow that, switch to PostgreSQL.
- Telegram should be configured in webhook mode with the public Railway URL.
