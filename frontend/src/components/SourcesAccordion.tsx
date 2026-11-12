import { useState } from "react";
import { AlertTriangle, BookOpen } from "lucide-react";
import type { Source } from "../api/client";
import { cn, pageLabel } from "../lib/utils";
import { sourceToTarget, type PdfTarget } from "./CitationChip";

interface Props {
  sources: Source[];
  onOpen: (target: PdfTarget) => void;
}

export function SourcesAccordion({ sources, onOpen }: Props) {
  const [showAll, setShowAll] = useState(false);
  if (!sources.length) return null;

  const cited = sources.filter((s) => s.cited);
  const visible = showAll || !cited.length ? sources : cited;

  return (
    <details className="group mt-3 rounded-lg border border-zinc-200 text-sm dark:border-zinc-800">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-3 py-2 text-zinc-600 select-none dark:text-zinc-400">
        <BookOpen className="size-4" />
        <span>
          {cited.length ? `${cited.length} cited source${cited.length > 1 ? "s" : ""}` : "Retrieved sources"}
        </span>
        <span className="ml-auto text-xs text-zinc-400 group-open:hidden">show</span>
      </summary>
      <ul className="divide-y divide-zinc-200 border-t border-zinc-200 dark:divide-zinc-800 dark:border-zinc-800">
        {visible.map((s) => (
          <li key={s.n}>
            <button
              onClick={() => onOpen(sourceToTarget(s))}
              className={cn(
                "block w-full px-3 py-2 text-left hover:bg-zinc-50 dark:hover:bg-zinc-900",
                !s.cited && "opacity-60",
              )}
            >
              <div className="flex items-center gap-2 text-xs">
                <span className="rounded-full bg-indigo-100 px-1.5 font-semibold text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
                  {s.n}
                </span>
                <span className="truncate font-medium">{s.filename}</span>
                <span className="shrink-0 text-zinc-500">{pageLabel(s.page_start, s.page_end)}</span>
                {s.support != null && (
                  <span className="ml-auto shrink-0 text-zinc-500" title="Claim ↔ source similarity">
                    support {Math.round(s.support * 100)}%
                  </span>
                )}
                {s.low_confidence && (
                  <span
                    className="flex shrink-0 items-center gap-1 text-amber-600"
                    title="The cited sentence is only weakly supported by this passage"
                  >
                    <AlertTriangle className="size-3" /> low confidence
                  </span>
                )}
              </div>
              <p className="mt-1 line-clamp-3 text-xs text-zinc-600 dark:text-zinc-400">{s.text}</p>
            </button>
          </li>
        ))}
      </ul>
      {cited.length > 0 && cited.length < sources.length && (
        <button
          onClick={() => setShowAll((v) => !v)}
          className="w-full border-t border-zinc-200 px-3 py-1.5 text-xs text-indigo-600 hover:underline dark:border-zinc-800 dark:text-indigo-400"
        >
          {showAll ? "Show cited only" : `Show all ${sources.length} retrieved`}
        </button>
      )}
    </details>
  );
}
