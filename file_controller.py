from __future__ import annotations
from fastapi import APIRouter, UploadFile, File

from services import storage_service

router = APIRouter(prefix="/files", tags=["files"])


@router.post("")
async def upload_file(file: UploadFile = File(...)):
    content = await file.read()
    content_hash = storage_service.store_file(content)
    return {"content_hash": content_hash, "filename": file.filename, "size_bytes": len(content)}
