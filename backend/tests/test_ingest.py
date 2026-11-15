import pytest

from app import ingest
from tests.conftest import make_pdf


def test_read_pdf_pages_extracts_text():
    pages = ingest.read_pdf_pages(make_pdf(["Refund policy is 30 days", "Shipping takes 3 days"]))
    assert len(pages) == 2
    assert "Refund policy" in pages[0]
    assert "Shipping" in pages[1]


def test_split_pages_keeps_page_numbers_and_skips_empty_pages():
    chunks = ingest.split_pages(
        ["a " * 300, "   ", "last page"],
        document_id="d1",
        filename="f.pdf",
        chunk_size=200,
        chunk_overlap=20,
    )
    assert len(chunks) > 2
    assert {c.metadata["page"] for c in chunks} == {1, 3}
    assert all(len(c.page_content) <= 200 for c in chunks)


def test_ingest_list_delete_roundtrip(store):
    result = ingest.ingest_pdf(store, make_pdf(["hello there"]), "a.pdf", chunk_size=200, chunk_overlap=20)
    assert result.chunks == 1 and result.pages == 1
    docs = ingest.list_documents(store)
    assert docs == [{"document_id": result.document_id, "filename": "a.pdf", "chunks": 1}]
    assert ingest.delete_document(store, result.document_id) == 1
    assert ingest.list_documents(store) == []


def test_invalid_pdf_raises():
    with pytest.raises(ingest.IngestError):
        ingest.read_pdf_pages(b"not a pdf")


def test_fastembed_wrapper_uses_passage_and_query_embed(monkeypatch):
    import numpy as np
    import fastembed

    from app.store import FastEmbedEmbeddings

    class Fake:
        def __init__(self, name, cache_dir=None):
            self.name, self.cache_dir = name, cache_dir

        def passage_embed(self, texts):
            return (np.array([1.0, float(len(t))]) for t in texts)

        def query_embed(self, text):
            return iter([np.array([0.0, 1.0])])

    monkeypatch.setattr(fastembed, "TextEmbedding", Fake)
    emb = FastEmbedEmbeddings("m", cache_dir="/tmp/x")
    assert emb.embed_documents(["ab", "c"]) == [[1.0, 2.0], [1.0, 1.0]]
    assert emb.embed_query("q") == [0.0, 1.0]
