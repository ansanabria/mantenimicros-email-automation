from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

from sqlalchemy.engine import make_url

from email_automation.config import get_settings
from email_automation.db import engine, init_db


async def reset_database() -> None:
    settings = get_settings()
    await engine.dispose()

    database_path = _sqlite_database_path(settings.database_url)
    if database_path.exists():
        database_path.unlink()

    if settings.attachment_storage_path.exists():
        shutil.rmtree(settings.attachment_storage_path)
    settings.attachment_storage_path.mkdir(parents=True, exist_ok=True)

    await init_db()

    print(f"Database reset at {database_path}")
    print(f"Attachment storage cleared at {settings.attachment_storage_path}")


def _sqlite_database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        raise RuntimeError("Database reset currently supports only sqlite databases")
    return Path(url.database)


def main() -> None:
    asyncio.run(reset_database())
