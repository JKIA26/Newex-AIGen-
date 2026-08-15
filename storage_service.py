"""
File storage, keyed by content-hash. In-memory stub — swap for real
object storage (per architecture.md's Object & Media Storage layer)
before production use.
"""
from __future__ import annotations
import hashlib
from typing import Any, Optional

_files: dict[str, dict[str, Any]] = {}


def store_file(content: bytes, extracted_fields: Optional[dict[str, Any]] = None) -> str:
    content_hash = hashlib.sha256(content).hexdigest()[:16]
    _files[content_hash] = {
        "content_hash": content_hash,
        "size_bytes": len(content),
        "extracted_fields": extracted_fields or {},
    }
    return content_hash


def get_file(content_hash: str) -> Optional[dict[str, Any]]:
    return _files.get(content_hash)
