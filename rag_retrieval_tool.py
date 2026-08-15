"""
rag.index_document / rag.retrieve — LlamaIndex-style indexing + retrieval.
Stubbed with an in-memory store; swap for a real vector index before
this handles production traffic.
"""
from __future__ import annotations
import uuid
from schemas.tool_schemas import (
    IndexDocumentInput,
    IndexDocumentOutput,
    RetrieveInput,
    RetrieveOutput,
    RetrieveChunk,
    ToolStatus,
)

# index_id -> list of (text, source)
_indexes: dict[str, list[tuple[str, str]]] = {}


def index_document(input_data: IndexDocumentInput) -> IndexDocumentOutput:
    index_id = f"idx_{uuid.uuid4().hex[:10]}"
    # TODO: real chunking + embedding. Stub: one "chunk" per document.
    _indexes[index_id] = [(f"content of {input_data.source_uri}", input_data.source_uri)]
    return IndexDocumentOutput(index_id=index_id, chunk_count=1, status=ToolStatus.SUCCESS)


def retrieve(input_data: RetrieveInput) -> RetrieveOutput:
    chunks = _indexes.get(input_data.index_id, [])
    # TODO: real similarity search. Stub: return up to top_k chunks verbatim.
    results = [
        RetrieveChunk(text=text, score=0.75, source=source)
        for text, source in chunks[: input_data.top_k]
    ]
    return RetrieveOutput(chunks=results)
