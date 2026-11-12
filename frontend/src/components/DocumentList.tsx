import { AlertCircle, CheckCircle2, FileText, Loader2, Trash2 } from "lucide-react";
import type { DocumentInfo } from "../api/client";
import { cn, formatBytes } from "../lib/utils";

interface Props {
  documents: DocumentInfo[];
  selected: Set<string>;
  onToggle: (id: string) => void;
  onDelete: (doc: DocumentInfo) => void;
  onOpen: (doc: DocumentInfo) => void;
}

function StatusIcon({ doc }: { doc: DocumentInfo }) {
  if (doc.status === "processing")
    return <Loader2 className="size-4 animate-spin text-indigo-500" aria-label="Processing" />;
  if (doc.status === "failed")
    return (
      <span title={doc.error ?? "Ingestion failed"}>
        <AlertCircle className="size-4 text-red-500" aria-label="Failed" />
      </span>
    );
  return <CheckCircle2 className="size-4 text-emerald-500" aria-label="Ready" />;
}

export function DocumentList({ documents, selected, onToggle, onDelete, onOpen }: Props) {
  if (!documents.length)
    return <p className="px-1 text-xs text-zinc-500">No documents yet. Upload a PDF to start.</p>;

  return (
    <ul className="space-y-1">
      {documents.map((doc) => (
        <li
          key={doc.id}
          className="group flex items-center gap-2 rounded-md px-1.5 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800/60"
        >
          <input
            type="checkbox"
            className="size-3.5 accent-indigo-600"
            checked={selected.has(doc.id)}
            disabled={doc.status !== "ready"}
            onChange={() => onToggle(doc.id)}
            title="Only ask these documents"
          />
          <button
            className="flex min-w-0 flex-1 items-center gap-2 text-left"
            onClick={() => doc.status === "ready" && onOpen(doc)}
            title={doc.filename}
          >
            <FileText className="size-4 shrink-0 text-zinc-400" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm">{doc.filename}</span>
              <span
                className={cn(
                  "block truncate text-xs",
                  doc.status === "failed" ? "text-red-500" : "text-zinc-500",
                )}
              >
                {doc.status === "processing"
                  ? "Processing…"
                  : doc.status === "failed"
                    ? (doc.error ?? "Failed")
                    : `${doc.page_count} pages · ${doc.chunk_count} chunks · ${formatBytes(doc.size_bytes)}`}
              </span>
            </span>
          </button>
          <StatusIcon doc={doc} />
          <button
            onClick={() => onDelete(doc)}
            className="text-zinc-400 opacity-0 group-hover:opacity-100 hover:text-red-500 focus:opacity-100"
            aria-label={`Delete ${doc.filename}`}
          >
            <Trash2 className="size-4" />
          </button>
        </li>
      ))}
    </ul>
  );
}
