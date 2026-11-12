import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import { ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { api } from "../api/client";
import type { PdfTarget } from "./CitationChip";

// react-pdf 11: the worker must be configured in the same module that renders <Document>.
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

const normalize = (s: string) =>
  s
    .toLowerCase()
    .replace(/-\s*\n\s*/g, "")
    .replace(/[\s­]+/g, " ")
    .trim();

const escapeHtml = (s: string) =>
  s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

interface Props {
  target: PdfTarget;
  onClose: () => void;
}

export function PdfPanel({ target, onClose }: Props) {
  const [page, setPage] = useState(target.page);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [width, setWidth] = useState(600);
  const containerRef = useRef<HTMLDivElement>(null);

  // Jump to the new cited page whenever a different citation is clicked.
  useEffect(() => setPage(target.page), [target]);

  // Fit the page to the panel width.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(200, entry.contentRect.width - 32)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const passage = normalize(target.text);
  const renderText = useCallback(
    ({ str }: { str: string }) => {
      const item = normalize(str);
      if (item.length >= 6 && passage.includes(item))
        return `<mark class="pdf-highlight">${escapeHtml(str)}</mark>`;
      return escapeHtml(str);
    },
    [passage],
  );

  return (
    <aside className="flex min-h-0 w-full flex-col border-l border-zinc-200 bg-zinc-50 lg:w-[45%] dark:border-zinc-800 dark:bg-zinc-900/50">
      <header className="flex items-center gap-2 border-b border-zinc-200 px-3 py-2 dark:border-zinc-800">
        <span className="min-w-0 flex-1 truncate text-sm font-medium" title={target.filename}>
          {target.filename}
        </span>
        <button
          onClick={() => setPage((p) => Math.max(1, p - 1))}
          disabled={page <= 1}
          className="rounded p-1 hover:bg-zinc-200 disabled:opacity-30 dark:hover:bg-zinc-800"
          aria-label="Previous page"
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="text-xs text-zinc-500 tabular-nums">
          p. {page}
          {numPages ? ` / ${numPages}` : ""}
        </span>
        <button
          onClick={() => setPage((p) => (numPages ? Math.min(numPages, p + 1) : p + 1))}
          disabled={numPages != null && page >= numPages}
          className="rounded p-1 hover:bg-zinc-200 disabled:opacity-30 dark:hover:bg-zinc-800"
          aria-label="Next page"
        >
          <ChevronRight className="size-4" />
        </button>
        <button
          onClick={onClose}
          className="ml-1 rounded p-1 hover:bg-zinc-200 dark:hover:bg-zinc-800"
          aria-label="Close PDF"
        >
          <X className="size-4" />
        </button>
      </header>

      <div ref={containerRef} className="scrollbar-thin min-h-0 flex-1 overflow-auto p-4">
        <Document
          file={api.documentFileUrl(target.docId)}
          onLoadSuccess={(pdf) => setNumPages(pdf.numPages)}
          loading={<Spinner />}
          error={<p className="text-sm text-red-500">Couldn't load this PDF.</p>}
        >
          <Page
            pageNumber={page}
            width={width}
            customTextRenderer={renderText}
            loading={<Spinner />}
            className="mx-auto shadow-md"
          />
        </Document>
      </div>
    </aside>
  );
}

function Spinner() {
  return (
    <div className="flex justify-center py-10">
      <Loader2 className="size-6 animate-spin text-zinc-400" />
    </div>
  );
}
