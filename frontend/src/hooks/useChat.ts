import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, streamChat, type Source } from "../api/client";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  pending?: boolean;
  error?: string;
  notFound?: boolean;
}

const uid = () => Math.random().toString(36).slice(2);

export function useChat() {
  const qc = useQueryClient();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(
    async (question: string, docIds: string[]) => {
      const assistantId = uid();
      setMessages((m) => [
        ...m,
        { id: uid(), role: "user", content: question, sources: [] },
        { id: assistantId, role: "assistant", content: "", sources: [], pending: true },
      ]);
      const update = (fn: (m: ChatMessage) => ChatMessage) =>
        setMessages((all) => all.map((m) => (m.id === assistantId ? fn(m) : m)));

      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      try {
        await streamChat(
          { question, conversation_id: conversationId, doc_ids: docIds.length ? docIds : null },
          {
            onMeta: ({ conversation_id }) => setConversationId(conversation_id),
            onToken: (t) => update((m) => ({ ...m, content: m.content + t })),
            onDone: (r) =>
              update((m) => ({
                ...m,
                content: r.answer,
                sources: r.sources,
                notFound: r.not_found,
                pending: false,
              })),
            onError: (message) => update((m) => ({ ...m, pending: false, error: message })),
          },
          controller.signal,
        );
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        update((m) => ({
          ...m,
          pending: false,
          error: aborted ? undefined : (err as Error).message,
          content: aborted ? `${m.content}\n\n_(stopped)_` : m.content,
        }));
      } finally {
        update((m) => (m.pending ? { ...m, pending: false } : m));
        setStreaming(false);
        abortRef.current = null;
        qc.invalidateQueries({ queryKey: ["conversations"] });
      }
    },
    [conversationId, qc],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([]);
  }, []);

  const load = useCallback(async (id: string) => {
    abortRef.current?.abort();
    const convo = await api.getConversation(id);
    setConversationId(convo.id);
    setMessages(
      convo.messages.map((m) => ({
        id: String(m.id),
        role: m.role,
        content: m.content,
        sources: m.sources,
        notFound: m.role === "assistant" && m.sources.length === 0,
      })),
    );
  }, []);

  return { conversationId, messages, streaming, send, stop, reset, load };
}
