"""Document ingestion: extract text, chunk it, embed the chunks, write them with the
document's retrieval scope so a scoped query never sees another scope's chunks."""

from __future__ import annotations

import io
from collections.abc import Sequence

from sqlalchemy.orm import Session

from enola.core.enums import DocumentStatus
from enola.core.errors import InvalidInputError
from enola.core.logging import get_logger
from enola.core.models.documents import Document, DocumentChunk
from enola.ingest.embeddings import Embedder

log = get_logger(__name__)

TEXT_MIMES = {"text/plain", "text/markdown", "text/csv", "application/json"}
CHUNK_CHARS = 900
CHUNK_OVERLAP = 150


def extract_text(filename: str, data: bytes, mime_type: str) -> str:
    lower = filename.lower()
    if mime_type == "application/pdf" or lower.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    if mime_type in TEXT_MIMES or lower.endswith((".txt", ".md", ".markdown", ".csv", ".json", ".py", ".ts", ".tsx")):
        return data.decode("utf-8", errors="replace")
    raise InvalidInputError(f"Cannot extract text from {filename} ({mime_type}). Upload PDF, Markdown or plain text.")


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Paragraph-aware fixed-size windows with overlap. Simple, and good enough for
    course notes and postings; a smarter splitter is a drop-in replacement here."""
    cleaned = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not cleaned:
        return []
    paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if len(candidate) <= size:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
            buffer = buffer[-overlap:] if overlap else ""
        while len(paragraph) > size:
            chunks.append((buffer + "\n\n" + paragraph[:size]).strip() if buffer else paragraph[:size])
            paragraph = paragraph[size - overlap :]
            buffer = ""
        buffer = (buffer + "\n\n" + paragraph).strip() if buffer else paragraph
    if buffer:
        chunks.append(buffer)
    return chunks


def ingest_document(db: Session, document: Document, data: bytes, embedder: Embedder) -> int:
    """Replace the document's chunks. Returns the chunk count. Marks the row failed on error."""
    try:
        text = extract_text(document.filename, data, document.mime_type)
        pieces = chunk_text(text)
        vectors = embedder.embed(pieces) if pieces else []
        document.chunks = [
            DocumentChunk(ordinal=i, text=piece, scope=document.scope, embedding=vector)
            for i, (piece, vector) in enumerate(zip(pieces, vectors, strict=True))
        ]
        document.chunk_count = len(pieces)
        document.status = DocumentStatus.INGESTED
        document.error = ""
        db.flush()
        log.info("document_ingested", document_id=document.id, chunks=len(pieces), scope=document.scope)
        return len(pieces)
    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error = str(exc)[:500]
        db.flush()
        log.warning("document_ingest_failed", document_id=document.id, error=str(exc))
        raise


def rescope_chunks(db: Session, document: Document, scope: str) -> None:
    document.scope = scope
    for chunk in document.chunks:
        chunk.scope = scope
    db.flush()


__all__: Sequence[str] = ("extract_text", "chunk_text", "ingest_document", "rescope_chunks")
