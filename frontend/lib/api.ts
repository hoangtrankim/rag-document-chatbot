import { SseParser } from "./sse";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export type DocumentInfo = { document_id: string; filename: string; chunks: number };
export type Source = { number: number; filename: string; page: number; text: string; score: number };
export type ChatTurn = { role: "user" | "assistant"; content: string };

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return typeof body.detail === "string" ? body.detail : `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const res = await fetch(`${API_URL}/documents`);
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.json();
}

export async function uploadDocument(file: File): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/documents`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await errorMessage(res));
}

export async function deleteDocument(id: string): Promise<void> {
  const res = await fetch(`${API_URL}/documents/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await errorMessage(res));
}

export type ChatHandlers = {
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
  onError: (message: string) => void;
};

export async function streamChat(
  question: string,
  history: ChatTurn[],
  handlers: ChatHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, history }),
    signal,
  });
  if (!res.ok || !res.body) {
    handlers.onError(await errorMessage(res));
    return;
  }
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  const parser = new SseParser();
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    for (const { event, data } of parser.push(value)) {
      const d = data as Record<string, unknown>;
      if (event === "sources") handlers.onSources(data as Source[]);
      else if (event === "token") handlers.onToken(String(d.text ?? ""));
      else if (event === "error") handlers.onError(String(d.message ?? "Something went wrong."));
    }
  }
}
