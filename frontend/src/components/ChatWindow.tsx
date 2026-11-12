import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUp, FileSearch, Square } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import { cn } from "../lib/utils";
import type { PdfTarget } from "./CitationChip";
import { MessageBubble } from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
  streaming: boolean;
  hasReadyDocs: boolean;
  filterCount: number;
  onSend: (question: string) => void;
  onStop: () => void;
  onOpenSource: (target: PdfTarget) => void;
}

const EXAMPLES = [
  "Summarize the main points of these documents.",
  "What are the key numbers or figures mentioned?",
  "What conclusions or recommendations are given?",
];

export function ChatWindow({
  messages,
  streaming,
  hasReadyDocs,
  filterCount,
  onSend,
  onStop,
  onOpenSource,
}: Props) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll as messages / tokens arrive.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Auto-grow the textarea.
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }, [input]);

  const canSend = hasReadyDocs && !streaming && input.trim().length > 0;

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!canSend) return;
    onSend(input.trim());
    setInput("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        {messages.length === 0 ? (
          <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center px-6 text-center">
            <FileSearch className="mb-3 size-10 text-indigo-500" />
            <h2 className="text-xl font-semibold">Chat with your PDFs</h2>
            <p className="mt-1 text-sm text-zinc-500">
              {hasReadyDocs
                ? "Ask a question. Every answer cites the file and page it came from."
                : "Upload a PDF in the sidebar to get started."}
            </p>
            {hasReadyDocs && (
              <div className="mt-6 grid w-full gap-2">
                {EXAMPLES.map((q) => (
                  <button
                    key={q}
                    onClick={() => onSend(q)}
                    className="rounded-lg border border-zinc-200 px-4 py-2 text-left text-sm hover:border-indigo-400 hover:bg-indigo-50 dark:border-zinc-800 dark:hover:bg-indigo-950/30"
                  >
                    {q}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {messages.map((m) => (
              <MessageBubble key={m.id} message={m} onOpen={onOpenSource} />
            ))}
          </div>
        )}
      </div>

      <form onSubmit={submit} className="mx-auto w-full max-w-3xl px-4 pb-4">
        {filterCount > 0 && (
          <p className="mb-1 px-1 text-xs text-indigo-600 dark:text-indigo-400">
            Asking only {filterCount} selected document{filterCount > 1 ? "s" : ""}
          </p>
        )}
        <div className="flex items-end gap-2 rounded-2xl border border-zinc-300 bg-white p-2 shadow-sm focus-within:border-indigo-500 dark:border-zinc-700 dark:bg-zinc-900">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={1}
            disabled={!hasReadyDocs}
            placeholder={hasReadyDocs ? "Ask about your documents…" : "Upload a PDF first"}
            className="max-h-[200px] flex-1 resize-none bg-transparent px-2 py-1.5 outline-none placeholder:text-zinc-400 disabled:cursor-not-allowed"
          />
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-white hover:bg-zinc-700 dark:bg-zinc-200 dark:text-zinc-900"
              aria-label="Stop generating"
            >
              <Square className="size-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="submit"
              disabled={!canSend}
              className={cn(
                "flex size-9 shrink-0 items-center justify-center rounded-full text-white transition-colors",
                canSend ? "bg-indigo-600 hover:bg-indigo-500" : "bg-zinc-300 dark:bg-zinc-700",
              )}
              aria-label="Send"
            >
              <ArrowUp className="size-4" />
            </button>
          )}
        </div>
        <p className="mt-1 px-1 text-[11px] text-zinc-400">Enter to send · Shift+Enter for a new line</p>
      </form>
    </div>
  );
}
