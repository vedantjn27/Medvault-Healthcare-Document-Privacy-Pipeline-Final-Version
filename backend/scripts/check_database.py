"""Validate the configured MongoDB connection, collections, and indexes."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings
from app.db.client import close_database_connection, connect_to_database


async def main() -> None:
    await connect_to_database(Settings())
    print("MongoDB initialization passed")
    await close_database_connection()


if __name__ == "__main__":
    asyncio.run(main())
