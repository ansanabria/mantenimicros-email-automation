from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from email_automation.config import get_settings
from email_automation.models import Base

settings = get_settings()
engine = create_async_engine(settings.database_url, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        yield session
