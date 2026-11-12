import { memo, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertCircle, SearchX } from "lucide-react";
import type { ChatMessage } from "../hooks/useChat";
import { cn } from "../lib/utils";
import { CitationChip, type PdfTarget } from "./CitationChip";
import { SourcesAccordion } from "./SourcesAccordion";

interface Props {
  message: ChatMessage;
  onOpen: (target: PdfTarget) => void;
}

/** Turn `[3]` into a markdown link `[3](#cite-3)` so we can render it as a chip. Leaves real links alone. */
const linkifyCitations = (text: string) => text.replace(/\[(\d{1,2})\](?!\()/g, "[$1](#cite-$1)");

function MessageBubbleImpl({ message, onOpen }: Props) {
  const components = useMemo<Components>(
    () => ({
      a: ({ href, children }) => {
        const m = href?.match(/^#cite-(\d+)$/);
        if (m) {
          const n = Number(m[1]);
          return <CitationChip n={n} source={message.sources.find((s) => s.n === n)} onOpen={onOpen} />;
        }
        return (
          <a href={href} target="_blank" rel="noreferrer">
            {children}
          </a>
        );
      },
    }),
    [message.sources, onOpen],
  );

  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-600 px-4 py-2 whitespace-pre-wrap text-white">
          {message.content}
        </div>
      </div>
    );
  }

  const empty = !message.content.trim();
  return (
    <div className="max-w-full">
      {message.notFound && !message.pending ? (
        <div className="flex items-start gap-2 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          <SearchX className="mt-0.5 size-4 shrink-0" />
          <span>{message.content || "I couldn't find that in your documents."}</span>
        </div>
      ) : (
        <div
          className={cn(
            "prose prose-zinc max-w-none dark:prose-invert prose-p:my-2 prose-pre:my-2",
            message.pending && "cursor-blink",
          )}
        >
          {empty && message.pending ? (
            <span className="text-sm text-zinc-500">Searching your documents…</span>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
              {linkifyCitations(message.content)}
            </ReactMarkdown>
          )}
        </div>
      )}

      {message.error && (
        <div className="mt-2 flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{message.error}</span>
        </div>
      )}

      {!message.pending && !message.notFound && (
        <SourcesAccordion sources={message.sources} onOpen={onOpen} />
      )}
    </div>
  );
}

export const MessageBubble = memo(MessageBubbleImpl);
