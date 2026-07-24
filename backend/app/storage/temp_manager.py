"""Secure per-document temporary storage and orphan cleanup."""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from time import time

from fastapi import UploadFile


UPLOAD_CHUNK_SIZE = 1024 * 1024
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


class StorageError(RuntimeError):
    """Base exception for safe temporary storage failures."""


class EmptyUploadError(StorageError):
    pass


class UploadTooLargeError(StorageError):
    pass


@dataclass(frozen=True)
class StoredUpload:
    path: Path
    size_bytes: int


def prepare_storage_root(root: Path) -> Path:
    """Create and resolve the configured storage root."""

    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def sanitize_filename(filename: str | None) -> str:
    """Return a traversal-safe, portable filename while retaining its extension."""

    candidate = Path((filename or "upload").replace("\\", "/")).name
    candidate = unicodedata.normalize("NFKC", candidate).strip().strip(".")
    candidate = _SAFE_COMPONENT.sub("_", candidate)
    if not candidate:
        candidate = "upload"

    stem = Path(candidate).stem[:120].rstrip(". ") or "upload"
    suffix = Path(candidate).suffix[:16].lower()
    return f"{stem}{suffix}"


def ensure_within_root(path: Path, root: Path) -> Path:
    """Resolve a path and reject any escape from the configured storage root."""

    resolved_root = root.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise StorageError("Temporary path escapes the configured storage root") from exc
    return resolved_path


def create_document_directory(root: Path, document_id: str) -> Path:
    """Create an isolated directory for a database-assigned document identifier."""

    if not re.fullmatch(r"[0-9a-f]{24}", document_id):
        raise StorageError("Invalid document directory identifier")
    resolved_root = prepare_storage_root(root)
    directory = ensure_within_root(resolved_root / document_id, resolved_root)
    directory.mkdir(mode=0o700, exist_ok=False)
    return directory


async def store_upload(upload: UploadFile, destination: Path, max_bytes: int) -> StoredUpload:
    """Stream an upload to disk with a hard byte limit and atomic cleanup on failure."""

    total = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as output:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > max_bytes:
                    raise UploadTooLargeError(f"Upload exceeds the {max_bytes}-byte limit")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if total == 0:
            raise EmptyUploadError("Uploaded file is empty")
        return StoredUpload(path=destination, size_bytes=total)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def delete_document_directory(directory: Path, root: Path) -> None:
    """Delete one validated document directory without following symlinks."""

    resolved_root = root.resolve()
    resolved_directory = ensure_within_root(directory, resolved_root)
    if resolved_directory == resolved_root:
        raise StorageError("Refusing to delete the storage root")
    if resolved_directory.is_symlink():
        resolved_directory.unlink(missing_ok=True)
    elif resolved_directory.exists():
        shutil.rmtree(resolved_directory)


def cleanup_expired_directories(root: Path, ttl_seconds: int, *, now: float | None = None) -> list[Path]:
    """Remove direct child directories older than the configured TTL."""

    resolved_root = prepare_storage_root(root)
    cutoff = (now if now is not None else time()) - ttl_seconds
    removed: list[Path] = []
    for child in resolved_root.iterdir():
        try:
            if child.stat(follow_symlinks=False).st_mtime > cutoff:
                continue
            if child.is_symlink():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed.append(child)
        except FileNotFoundError:
            continue
    return removed


async def periodic_cleanup(
    root: Path,
    ttl_seconds: int,
    interval_seconds: int,
    stop_event: asyncio.Event,
) -> None:
    """Sweep orphaned temporary data until application shutdown."""

    while not stop_event.is_set():
        await asyncio.to_thread(cleanup_expired_directories, root, ttl_seconds)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue
