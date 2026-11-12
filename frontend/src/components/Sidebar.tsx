import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FileSearch, MessageSquare, Moon, Plus, Sun, Trash2 } from "lucide-react";
import { api, type DocumentInfo, type Health } from "../api/client";
import { cn } from "../lib/utils";
import { DocumentList } from "./DocumentList";
import { UploadDropzone } from "./UploadDropzone";

interface Props {
  documents: DocumentInfo[];
  uploading: boolean;
  onUpload: (files: File[]) => void;
  onDeleteDocument: (doc: DocumentInfo) => void;
  onOpenDocument: (doc: DocumentInfo) => void;
  selected: Set<string>;
  onToggleSelected: (id: string) => void;
  onClearSelected: () => void;
  activeConversationId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  health?: Health;
  healthError: boolean;
}

function useDarkMode() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {
      /* storage unavailable */
    }
    setDark(next);
  };
  return [dark, toggle] as const;
}

export function Sidebar(props: Props) {
  const [dark, toggleDark] = useDarkMode();
  const conversations = useQuery({ queryKey: ["conversations"], queryFn: api.listConversations });
  const ok = !props.healthError && props.health?.llm_ok;

  return (
    <nav className="flex h-full w-72 shrink-0 flex-col border-r border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/60">
      <div className="flex items-center gap-2 px-4 pt-4 pb-3">
        <FileSearch className="size-5 text-indigo-500" />
        <span className="text-lg font-semibold tracking-tight">DocChat</span>
      </div>

      <div className="px-3">
        <button
          onClick={props.onNewChat}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          <Plus className="size-4" /> New chat
        </button>
      </div>

      <div className="scrollbar-thin mt-3 min-h-0 flex-1 space-y-5 overflow-y-auto px-3 pb-3">
        <section className="space-y-2">
          <UploadDropzone onFiles={props.onUpload} uploading={props.uploading} />
          <div className="flex items-center justify-between px-1">
            <h3 className="text-xs font-semibold tracking-wide text-zinc-500 uppercase">Documents</h3>
            {props.selected.size > 0 && (
              <button
                onClick={props.onClearSelected}
                className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
              >
                Clear filter ({props.selected.size})
              </button>
            )}
          </div>
          <DocumentList
            documents={props.documents}
            selected={props.selected}
            onToggle={props.onToggleSelected}
            onDelete={props.onDeleteDocument}
            onOpen={props.onOpenDocument}
          />
        </section>

        <section className="space-y-1">
          <h3 className="px-1 text-xs font-semibold tracking-wide text-zinc-500 uppercase">Chats</h3>
          {!conversations.data?.length && <p className="px-1 text-xs text-zinc-500">No chats yet.</p>}
          <ul className="space-y-0.5">
            {conversations.data?.map((c) => (
              <li key={c.id} className="group flex items-center">
                <button
                  onClick={() => props.onSelectConversation(c.id)}
                  className={cn(
                    "flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-800/60",
                    c.id === props.activeConversationId &&
                      "bg-zinc-200/70 font-medium dark:bg-zinc-800",
                  )}
                  title={c.title}
                >
                  <MessageSquare className="size-3.5 shrink-0 text-zinc-400" />
                  <span className="truncate">{c.title || "Untitled chat"}</span>
                </button>
                <button
                  onClick={() => props.onDeleteConversation(c.id)}
                  className="px-1 text-zinc-400 opacity-0 group-hover:opacity-100 hover:text-red-500 focus:opacity-100"
                  aria-label="Delete chat"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <footer className="flex items-center gap-2 border-t border-zinc-200 px-4 py-3 text-xs text-zinc-500 dark:border-zinc-800">
        <span
          className={cn("size-2 shrink-0 rounded-full", ok ? "bg-emerald-500" : "bg-amber-500")}
          title={props.healthError ? "Backend unreachable" : props.health?.llm_message}
        />
        <span className="min-w-0 flex-1 truncate">
          {props.healthError
            ? "Backend offline"
            : props.health
              ? `${props.health.llm_model} · ${props.health.chunks_indexed} chunks`
              : "Checking…"}
        </span>
        <button
          onClick={toggleDark}
          className="rounded p-1 hover:bg-zinc-200 dark:hover:bg-zinc-800"
          aria-label="Toggle dark mode"
        >
          {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </footer>
    </nav>
  );
}
