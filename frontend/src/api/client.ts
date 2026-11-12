export type DocStatus = "processing" | "ready" | "failed";

export interface DocumentInfo {
  id: string;
  filename: string;
  status: DocStatus;
  error: string | null;
  page_count: number;
  chunk_count: number;
  size_bytes: number;
  created_at: string;
}

export interface Source {
  n: number;
  doc_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  text: string;
  similarity: number | null;
  cited: boolean;
  support: number | null;
  low_confidence: boolean;
}

export interface ChatResult {
  answer: string;
  sources: Source[];
  standalone_question: string;
  not_found: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: { id: number; role: "user" | "assistant"; content: string; sources: Source[] }[];
}

export interface Health {
  llm_ok: boolean;
  llm_message: string;
  llm_model: string;
  embedding_model: string;
  reranker: string | null;
  chunks_indexed: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return (res.status === 204 ? undefined : await res.json()) as T;
}

export const api = {
  health: () => request<Health>("/api/health"),
  listDocuments: () => request<DocumentInfo[]>("/api/documents"),
  uploadDocuments: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<DocumentInfo[]>("/api/documents", { method: "POST", body: form });
  },
  deleteDocument: (id: string) => request<void>(`/api/documents/${id}`, { method: "DELETE" }),
  documentFileUrl: (id: string) => `/api/documents/${id}/file`,
  listConversations: () => request<ConversationSummary[]>("/api/conversations"),
  getConversation: (id: string) => request<ConversationDetail>(`/api/conversations/${id}`),
  deleteConversation: (id: string) =>
    request<void>(`/api/conversations/${id}`, { method: "DELETE" }),
};

export interface ChatHandlers {
  onMeta: (meta: { conversation_id: string }) => void;
  onToken: (text: string) => void;
  onDone: (result: ChatResult) => void;
  onError: (message: string) => void;
}

/** POST /api/chat and parse the Server-Sent Events stream. */
export async function streamChat(
  body: { question: string; conversation_id: string | null; doc_ids: string[] | null },
  handlers: ChatHandlers,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => "");
    throw new Error(text || `Chat request failed (${res.status})`);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      dispatch(buffer.slice(0, boundary), handlers);
      buffer = buffer.slice(boundary + 2);
    }
  }
}

function dispatch(raw: string, h: ChatHandlers) {
  let event = "message";
  const data: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return;
  const payload = JSON.parse(data.join("\n"));
  if (event === "meta") h.onMeta(payload);
  else if (event === "token") h.onToken(payload);
  else if (event === "done") h.onDone(payload);
  else if (event === "error") h.onError(payload.message);
}
