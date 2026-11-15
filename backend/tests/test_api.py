import json

from tests.conftest import FakeClient, make_pdf
from app.main import app, get_client


def parse_sse(text: str) -> list[tuple[str, object]]:
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def upload(client, pages, name="policy.pdf"):
    return client.post("/documents", files={"file": (name, make_pdf(pages), "application/pdf")})


def test_upload_and_list(client):
    r = upload(client, ["Refunds are accepted within 30 days."])
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "policy.pdf" and body["chunks"] == 1
    assert client.get("/documents").json()[0]["document_id"] == body["document_id"]


def test_upload_rejects_non_pdf(client):
    r = client.post("/documents", files={"file": ("notes.txt", b"hi", "text/plain")})
    assert r.status_code == 400


def test_upload_rejects_pdf_without_text(client):
    r = upload(client, [""])
    assert r.status_code == 422


def test_delete_document(client):
    doc_id = upload(client, ["abc"]).json()["document_id"]
    assert client.delete(f"/documents/{doc_id}").status_code == 200
    assert client.delete(f"/documents/{doc_id}").status_code == 404


def test_chat_streams_sources_then_tokens(client, fake_client):
    upload(client, ["Refunds are accepted within 30 days.", "Shipping takes 3 days."])
    r = client.post("/chat", json={"question": "What is the refund policy?"})
    assert r.status_code == 200
    events = parse_sse(r.text)
    assert events[0][0] == "sources"
    assert {s["page"] for s in events[0][1]} <= {1, 2}
    assert [e for e, _ in events[1:]] == ["token", "token", "done"]
    assert "".join(d["text"] for e, d in events if e == "token") == "Hello world [1]"

    call = fake_client.calls[0]
    last = call["messages"][-1]["content"]
    assert "<sources>" in last and "Question: What is the refund policy?" in last
    assert call["fallbacks"] == "default"


def test_chat_includes_history(client, fake_client):
    upload(client, ["Some text"])
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    client.post("/chat", json={"question": "and?", "history": history})
    msgs = fake_client.calls[0]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]


def test_chat_without_documents_skips_claude(client, fake_client):
    events = parse_sse(client.post("/chat", json={"question": "hi"}).text)
    assert events[0] == ("sources", [])
    assert events[-1][0] == "done"
    assert fake_client.calls == []


def test_chat_reports_refusal(client):
    app.dependency_overrides[get_client] = lambda: FakeClient(chunks=[], stop_reason="refusal")
    upload(client, ["Some text"])
    events = parse_sse(client.post("/chat", json={"question": "x"}).text)
    assert events[-1][0] == "error"
