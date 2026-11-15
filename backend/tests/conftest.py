import pytest
from fastapi.testclient import TestClient
from langchain_chroma import Chroma
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.config import Settings, get_settings
from app.main import app, get_client
from app.store import get_store


def make_pdf(pages: list[str]) -> bytes:
    """Build a tiny valid PDF with one line of text per page (no extra libraries)."""
    objects: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(n))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    font_id = 3 + n * 2
    for i, text in enumerate(pages):
        content_id = 4 + i * 2
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode()
        )
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


class FakeStream:
    def __init__(self, chunks, stop_reason="end_turn"):
        self.chunks = chunks
        self.stop_reason = stop_reason

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    @property
    def text_stream(self):
        async def gen():
            for c in self.chunks:
                yield c

        return gen()

    async def get_final_message(self):
        class Final:
            stop_reason = self.stop_reason

        return Final()


class FakeClient:
    def __init__(self, chunks=("Hello ", "world [1]"), stop_reason="end_turn"):
        self.calls: list[dict] = []
        outer = self

        class Messages:
            def stream(self, **kwargs):
                outer.calls.append(kwargs)
                return FakeStream(list(chunks), stop_reason)

        class Beta:
            messages = Messages()

        self.beta = Beta()


@pytest.fixture
def store(tmp_path):
    return Chroma(
        collection_name="test",
        embedding_function=DeterministicFakeEmbedding(size=64),
        persist_directory=str(tmp_path / "chroma"),
        collection_metadata={"hnsw:space": "cosine"},
    )


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def client(store, fake_client):
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_client] = lambda: fake_client
    app.dependency_overrides[get_settings] = lambda: Settings(chunk_size=200, chunk_overlap=20, top_k=3)
    yield TestClient(app)
    app.dependency_overrides.clear()
