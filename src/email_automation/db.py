from collections.abc import AsyncIterator

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from email_automation.config import get_settings
from email_automation.models import Base

settings = get_settings()
engine = create_async_engine(settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        columns = await connection.run_sync(
            lambda sync_conn: {
                column["name"]
                for column in inspect(sync_conn).get_columns("email_messages")
            }
        )
        if "is_read" not in columns:
            await connection.execute(
                text(
                    "ALTER TABLE email_messages ADD COLUMN is_read BOOLEAN NOT NULL DEFAULT 0"
                )
            )
        if "read_at" not in columns:
            await connection.execute(
                text("ALTER TABLE email_messages ADD COLUMN read_at DATETIME")
            )


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
