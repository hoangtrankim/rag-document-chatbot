import json
from collections.abc import AsyncIterator
from typing import Literal

import anthropic
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import ingest, rag
from .config import Settings, get_settings
from .store import get_store

app = FastAPI(title="RAG Document Chatbot", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=get_settings().anthropic_api_key)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4_000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/documents")
def documents(store=Depends(get_store)) -> list[dict]:
    return ingest.list_documents(store)


@app.post("/documents", status_code=201)
async def upload(
    file: UploadFile = File(...),
    store=Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    name = file.filename or "document.pdf"
    if not name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
    try:
        result = await run_in_threadpool(
            ingest.ingest_pdf,
            store,
            data,
            name,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    except ingest.IngestError as exc:
        raise HTTPException(422, str(exc)) from exc
    return result.__dict__


@app.delete("/documents/{document_id}")
def remove(document_id: str, store=Depends(get_store)) -> dict:
    removed = ingest.delete_document(store, document_id)
    if not removed:
        raise HTTPException(404, "Document not found.")
    return {"deleted_chunks": removed}


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(
    body: ChatRequest,
    store=Depends(get_store),
    settings: Settings = Depends(get_settings),
    client: anthropic.AsyncAnthropic = Depends(get_client),
) -> StreamingResponse:
    """Stream an answer as Server-Sent Events: `sources`, then `token`s, then `done` or `error`."""
    sources = await run_in_threadpool(rag.retrieve, store, body.question, settings.top_k)
    messages = rag.build_messages(
        [t.model_dump() for t in body.history], body.question, sources
    )

    async def events() -> AsyncIterator[str]:
        yield sse("sources", rag.sources_payload(sources))
        if not sources:
            yield sse("token", {"text": "No documents uploaded yet. Upload a PDF first, then ask your question."})
            yield sse("done", {})
            return
        try:
            async for text in rag.stream_answer(
                client,
                model=settings.claude_model,
                effort=settings.claude_effort,
                max_tokens=settings.max_answer_tokens,
                messages=messages,
            ):
                yield sse("token", {"text": text})
            yield sse("done", {})
        except rag.RefusalError as exc:
            yield sse("error", {"message": str(exc)})
        except anthropic.RateLimitError:
            yield sse("error", {"message": "Too many requests right now. Please try again in a minute."})
        except anthropic.APIStatusError as exc:
            yield sse("error", {"message": f"Claude API error ({exc.status_code})."})
        except anthropic.APIConnectionError:
            yield sse("error", {"message": "Could not reach the Claude API."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
