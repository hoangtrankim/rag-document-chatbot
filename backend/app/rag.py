"""Retrieval-augmented answers: find relevant chunks, then ask Claude to answer from them."""

from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass

from anthropic import AsyncAnthropic
from langchain_chroma import Chroma

SYSTEM_PROMPT = """You answer questions using only the document excerpts provided in <sources>.

Rules:
- Base every statement on the sources. If they do not contain the answer, say you could not find it in the uploaded documents and suggest what to upload or ask instead.
- Cite sources inline with their number in square brackets, like [1] or [2][3], right after the statement they support.
- Answer in the same language as the question.
- Be concise: lead with the direct answer, then supporting detail. Use short paragraphs or bullet lists."""


@dataclass
class Source:
    number: int
    filename: str
    page: int
    text: str
    score: float


def retrieve(store: Chroma, question: str, k: int) -> list[Source]:
    # The collection uses cosine distance, so similarity = 1 - distance.
    results = store.similarity_search_with_score(question, k=k)
    return [
        Source(
            number=i,
            filename=doc.metadata.get("filename", "unknown"),
            page=int(doc.metadata.get("page", 0)),
            text=doc.page_content,
            score=round(1.0 - float(distance), 4),
        )
        for i, (doc, distance) in enumerate(results, start=1)
    ]


def format_sources(sources: list[Source]) -> str:
    parts = [
        f'<source number="{s.number}" file="{s.filename}" page="{s.page}">\n{s.text}\n</source>'
        for s in sources
    ]
    return "<sources>\n" + "\n".join(parts) + "\n</sources>"


def build_messages(history: list[dict], question: str, sources: list[Source]) -> list[dict]:
    """Earlier turns stay as plain text; the newest question carries the sources."""
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append(
        {
            "role": "user",
            "content": f"{format_sources(sources)}\n\nQuestion: {question}",
        }
    )
    return messages


def sources_payload(sources: list[Source]) -> list[dict]:
    return [asdict(s) for s in sources]


async def stream_answer(
    client: AsyncAnthropic,
    *,
    model: str,
    effort: str,
    max_tokens: int,
    messages: list[dict],
) -> AsyncIterator[str]:
    """Yield answer text as Claude writes it. Raises RefusalError if Claude declines."""
    async with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=messages,
        output_config={"effort": effort},
        # If the model declines on safety grounds, the API retries on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        async for text in stream.text_stream:
            yield text
        final = await stream.get_final_message()
    if final.stop_reason == "refusal":
        raise RefusalError("Claude declined to answer this question.")


class RefusalError(RuntimeError):
    pass
