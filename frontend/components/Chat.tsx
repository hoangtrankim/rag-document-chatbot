"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Answer from "./Answer";
import {
  deleteDocument,
  listDocuments,
  streamChat,
  uploadDocument,
  type ChatTurn,
  type DocumentInfo,
  type Source,
} from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  error?: string;
  pending?: boolean;
};

const EXAMPLES = ["Summarize this document", "What are the key dates and deadlines?", "List the main risks mentioned"];

export default function Chat() {
  const [docs, setDocs] = useState<DocumentInfo[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [activeSource, setActiveSource] = useState<Source | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const abort = useRef<AbortController | null>(null);

  const refreshDocs = useCallback(async () => {
    try {
      setDocs(await listDocuments());
    } catch (e) {
      setNotice(`Can't reach the API: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    refreshDocs();
  }, [refreshDocs]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function handleFiles(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    setNotice(null);
    try {
      for (const file of Array.from(files)) await uploadDocument(file);
      await refreshDocs();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteDocument(id);
      await refreshDocs();
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  function updateLast(fn: (m: Message) => Message) {
    setMessages((prev) => [...prev.slice(0, -1), fn(prev[prev.length - 1])]);
  }

  async function ask(question: string) {
    question = question.trim();
    if (!question || busy) return;
    const history: ChatTurn[] = messages
      .filter((m) => !m.error && m.content)
      .slice(-10)
      .map((m) => ({ role: m.role, content: m.content }));
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      { role: "assistant", content: "", pending: true },
    ]);
    setInput("");
    setBusy(true);
    abort.current = new AbortController();
    try {
      await streamChat(
        question,
        history,
        {
          onSources: (sources) => updateLast((m) => ({ ...m, sources })),
          onToken: (t) => updateLast((m) => ({ ...m, content: m.content + t })),
          onError: (error) => updateLast((m) => ({ ...m, error })),
        },
        abort.current.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") updateLast((m) => ({ ...m, error: (e as Error).message }));
    } finally {
      updateLast((m) => ({ ...m, pending: false }));
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">◆</span> DocChat
        </div>
        <p className="tagline">Ask questions about your PDFs. Every answer cites its sources.</p>

        <div
          className={`dropzone ${dragOver ? "over" : ""}`}
          onClick={() => fileInput.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
        >
          {uploading ? "Processing…" : "Drop PDFs here or click to upload"}
          <input
            ref={fileInput}
            type="file"
            accept="application/pdf"
            multiple
            hidden
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>

        <h2>Documents</h2>
        {docs.length === 0 ? (
          <p className="muted">No documents yet.</p>
        ) : (
          <ul className="docs">
            {docs.map((d) => (
              <li key={d.document_id}>
                <span className="docname" title={d.filename}>
                  {d.filename}
                </span>
                <span className="muted small">{d.chunks} chunks</span>
                <button className="icon" onClick={() => handleDelete(d.document_id)} aria-label={`Delete ${d.filename}`}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {notice && <p className="notice">{notice}</p>}
      </aside>

      <main className="main">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              <h1>Ask your documents anything</h1>
              <p className="muted">Upload a PDF on the left, then try:</p>
              <div className="examples">
                {EXAMPLES.map((q) => (
                  <button key={q} onClick={() => ask(q)} disabled={busy}>
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.role === "user" ? (
                <p>{m.content}</p>
              ) : (
                <>
                  {m.content ? (
                    <Answer
                      text={m.content}
                      onCite={(n) => setActiveSource(m.sources?.find((s) => s.number === n) ?? null)}
                      validNumbers={new Set((m.sources ?? []).map((s) => s.number))}
                    />
                  ) : (
                    m.pending && !m.error && <p className="muted typing">Searching your documents…</p>
                  )}
                  {m.error && <p className="error">{m.error}</p>}
                  {!m.pending && m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      {m.sources.map((s) => (
                        <button key={s.number} className="source" onClick={() => setActiveSource(s)}>
                          <b>{s.number}</b> {s.filename} · p.{s.page}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
          <div ref={bottom} />
        </div>

        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(input);
              }
            }}
            placeholder="Ask a question about your documents…"
            rows={1}
          />
          {busy ? (
            <button type="button" onClick={() => abort.current?.abort()}>
              Stop
            </button>
          ) : (
            <button type="submit" disabled={!input.trim()}>
              Send
            </button>
          )}
        </form>
      </main>

      {activeSource && (
        <div className="overlay" onClick={() => setActiveSource(null)}>
          <div className="panel" onClick={(e) => e.stopPropagation()}>
            <div className="panel-head">
              <b>
                Source {activeSource.number}: {activeSource.filename}, page {activeSource.page}
              </b>
              <button className="icon" onClick={() => setActiveSource(null)} aria-label="Close">
                ×
              </button>
            </div>
            <p className="muted small">Similarity {activeSource.score.toFixed(2)}</p>
            <blockquote>{activeSource.text}</blockquote>
          </div>
        </div>
      )}
    </div>
  );
}
