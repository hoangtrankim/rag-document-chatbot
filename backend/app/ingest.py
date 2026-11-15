"""Turn an uploaded PDF into searchable chunks."""

import io
import uuid
from dataclasses import dataclass

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader


class IngestError(ValueError):
    pass


@dataclass
class IngestResult:
    document_id: str
    filename: str
    pages: int
    chunks: int


def read_pdf_pages(data: bytes) -> list[str]:
    try:
        reader = PdfReader(io.BytesIO(data))
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:  # pypdf raises many error types for broken files
        raise IngestError(f"Could not read PDF: {exc}") from exc


def split_pages(
    pages: list[str],
    *,
    document_id: str,
    filename: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks: list[Document] = []
    for page_number, text in enumerate(pages, start=1):
        text = text.strip()
        if not text:
            continue
        for piece in splitter.split_text(text):
            chunks.append(
                Document(
                    page_content=piece,
                    metadata={
                        "document_id": document_id,
                        "filename": filename,
                        "page": page_number,
                    },
                )
            )
    return chunks


def ingest_pdf(
    store: Chroma,
    data: bytes,
    filename: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> IngestResult:
    pages = read_pdf_pages(data)
    document_id = uuid.uuid4().hex
    chunks = split_pages(
        pages,
        document_id=document_id,
        filename=filename,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    if not chunks:
        raise IngestError(
            "No text found in this PDF. Scanned PDFs need OCR before upload."
        )
    ids = [f"{document_id}-{i}" for i in range(len(chunks))]
    store.add_documents(chunks, ids=ids)
    return IngestResult(document_id, filename, len(pages), len(chunks))


def list_documents(store: Chroma) -> list[dict]:
    rows = store.get(include=["metadatas"])["metadatas"] or []
    docs: dict[str, dict] = {}
    for meta in rows:
        doc_id = meta["document_id"]
        entry = docs.setdefault(
            doc_id, {"document_id": doc_id, "filename": meta["filename"], "chunks": 0}
        )
        entry["chunks"] += 1
    return sorted(docs.values(), key=lambda d: d["filename"].lower())


def delete_document(store: Chroma, document_id: str) -> int:
    found = store.get(where={"document_id": document_id})["ids"]
    if found:
        store.delete(ids=found)
    return len(found)
