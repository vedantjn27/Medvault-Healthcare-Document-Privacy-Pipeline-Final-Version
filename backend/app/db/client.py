"""MongoDB client lifecycle and Beanie initialization."""

from __future__ import annotations

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import Settings
from app.db.models import DOCUMENT_MODELS


_client: AsyncIOMotorClient | None = None


async def connect_to_database(settings: Settings) -> AsyncIOMotorClient:
    """Connect, verify MongoDB availability, and initialize all Beanie models."""

    global _client
    if _client is not None:
        return _client

    uri = settings.mongodb_uri.get_secret_value()
    client = AsyncIOMotorClient(
        uri,
        appname="medvault-api",
        serverSelectionTimeoutMS=10_000,
        connectTimeoutMS=10_000,
        uuidRepresentation="standard",
    )
    try:
        await client.admin.command("ping")
        await init_beanie(
            database=client[settings.mongodb_db_name],
            document_models=list(DOCUMENT_MODELS),
        )
    except Exception:
        client.close()
        raise

    _client = client
    return client


async def close_database_connection() -> None:
    """Close the process-wide MongoDB client, if initialized."""

    global _client
    if _client is not None:
        _client.close()
        _client = None


def get_database_client() -> AsyncIOMotorClient:
    """Return the initialized client or fail clearly during invalid lifecycle use."""

    if _client is None:
        raise RuntimeError("MongoDB has not been initialized")
    return _client
