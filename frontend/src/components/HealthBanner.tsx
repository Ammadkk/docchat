import { AlertTriangle } from "lucide-react";
import type { Health } from "../api/client";

export function HealthBanner({ health, error }: { health?: Health; error: Error | null }) {
  let message: string | null = null;
  if (error) message = "Can't reach the DocChat backend. Is uvicorn running on port 8000?";
  else if (health && !health.llm_ok)
    message = `${health.llm_message} (start Ollama and run: ollama pull ${health.llm_model})`;
  if (!message) return null;

  return (
    <div className="flex items-start gap-2 border-b border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/60 dark:text-amber-200">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
