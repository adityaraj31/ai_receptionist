from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

connect_args: dict[str, object] = {}
if settings.database_url.startswith("postgresql+asyncpg"):
    # Safe with Supabase/Neon poolers, which do not support prepared statements.
    connect_args["statement_cache_size"] = 0
    if settings.database_ssl:
        connect_args["ssl"] = settings.database_ssl

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
