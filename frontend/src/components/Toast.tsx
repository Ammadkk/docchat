import { CheckCircle2, X, XCircle } from "lucide-react";
import { cn } from "../lib/utils";

export interface ToastItem {
  id: number;
  kind: "success" | "error";
  message: string;
}

export function Toasts({ toasts, onDismiss }: { toasts: ToastItem[]; onDismiss: (id: number) => void }) {
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={cn(
            "pointer-events-auto flex max-w-sm items-start gap-2 rounded-lg border bg-white px-3 py-2 text-sm shadow-lg dark:bg-zinc-900",
            t.kind === "success"
              ? "border-emerald-300 dark:border-emerald-800"
              : "border-red-300 dark:border-red-800",
          )}
        >
          {t.kind === "success" ? (
            <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-500" />
          ) : (
            <XCircle className="mt-0.5 size-4 shrink-0 text-red-500" />
          )}
          <span className="flex-1 break-words">{t.message}</span>
          <button
            onClick={() => onDismiss(t.id)}
            className="text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200"
            aria-label="Dismiss"
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
