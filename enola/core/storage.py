"""File storage abstraction. v1 writes to local disk; the interface is what the rest
of the code depends on, so a move to object storage is a new class, not a rewrite."""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from typing import Protocol

from enola.core.config import get_settings
from enola.core.errors import NotFoundError


class Storage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


def make_key(filename: str) -> str:
    """A collision-proof key that still hints at the original name."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-")[:80] or "file"
    return f"{secrets.token_hex(8)}-{safe}"


class LocalDiskStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise NotFoundError("Invalid storage key")
        return path

    def put(self, key: str, data: bytes) -> None:
        self._path(key).write_bytes(data)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise NotFoundError(f"No stored file for {key}")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


def get_storage() -> Storage:
    return LocalDiskStorage(get_settings().storage_root)
