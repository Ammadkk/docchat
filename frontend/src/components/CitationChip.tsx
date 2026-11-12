import type { Source } from "../api/client";
import { cn, pageLabel } from "../lib/utils";

export interface PdfTarget {
  docId: string;
  filename: string;
  page: number;
  text: string;
}

export const sourceToTarget = (s: Source): PdfTarget => ({
  docId: s.doc_id,
  filename: s.filename,
  page: s.page_start,
  text: s.text,
});

interface Props {
  n: number;
  source?: Source;
  onOpen: (target: PdfTarget) => void;
}

export function CitationChip({ n, source, onOpen }: Props) {
  const title = source
    ? `${source.filename}, ${pageLabel(source.page_start, source.page_end)}${
        source.low_confidence ? " (weak support: verify this claim)" : ""
      }`
    : "Source unavailable";

  return (
    <button
      type="button"
      title={title}
      disabled={!source}
      onClick={() => source && onOpen(sourceToTarget(source))}
      className={cn(
        "mx-0.5 inline-flex h-[1.15rem] min-w-[1.15rem] -translate-y-px items-center justify-center rounded-full px-1 align-middle text-[0.7rem] leading-none font-semibold no-underline transition-colors",
        !source && "cursor-default bg-zinc-200 text-zinc-500 dark:bg-zinc-800",
        source &&
          !source.low_confidence &&
          "bg-indigo-100 text-indigo-700 hover:bg-indigo-600 hover:text-white dark:bg-indigo-950 dark:text-indigo-300",
        source?.low_confidence &&
          "border border-dashed border-amber-500 bg-amber-50 text-amber-700 hover:bg-amber-500 hover:text-white dark:bg-amber-950/50 dark:text-amber-300",
      )}
    >
      {n}
    </button>
  );
}
