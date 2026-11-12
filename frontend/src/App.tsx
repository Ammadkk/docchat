import { Suspense, lazy, useCallback, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Menu } from "lucide-react";
import { api, type DocumentInfo } from "./api/client";
import { useChat } from "./hooks/useChat";
import { useDocuments } from "./hooks/useDocuments";
import { cn } from "./lib/utils";
import { ChatWindow } from "./components/ChatWindow";
import type { PdfTarget } from "./components/CitationChip";
import { HealthBanner } from "./components/HealthBanner";
import { Sidebar } from "./components/Sidebar";
import { Toasts, type ToastItem } from "./components/Toast";

// pdf.js is large: load the viewer only when a citation is first opened.
const PdfPanel = lazy(() => import("./components/PdfPanel").then((m) => ({ default: m.PdfPanel })));

let toastId = 0;

export default function App() {
  const qc = useQueryClient();
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pdfTarget, setPdfTarget] = useState<PdfTarget | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const toast = useCallback((kind: ToastItem["kind"], message: string) => {
    const id = ++toastId;
    setToasts((t) => [...t, { id, kind, message }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);

  const onStatusChange = useCallback(
    (doc: DocumentInfo) => {
      if (doc.status === "ready") toast("success", `${doc.filename} is ready`);
      else toast("error", `${doc.filename} failed: ${doc.error ?? "unknown error"}`);
      qc.invalidateQueries({ queryKey: ["health"] });
    },
    [toast, qc],
  );

  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 15000 });
  const { documents, upload, remove } = useDocuments(onStatusChange);
  const chat = useChat();

  const readyIds = new Set(documents.filter((d) => d.status === "ready").map((d) => d.id));
  const activeFilter = [...selected].filter((id) => readyIds.has(id));

  const handleUpload = (files: File[]) =>
    upload.mutate(files, { onError: (e) => toast("error", `Upload failed: ${e.message}`) });

  const handleDeleteDocument = (doc: DocumentInfo) => {
    if (!confirm(`Delete "${doc.filename}" and its index?`)) return;
    remove.mutate(doc.id, {
      onSuccess: () => {
        setSelected((s) => {
          const next = new Set(s);
          next.delete(doc.id);
          return next;
        });
        if (pdfTarget?.docId === doc.id) setPdfTarget(null);
        qc.invalidateQueries({ queryKey: ["health"] });
      },
      onError: (e) => toast("error", `Delete failed: ${e.message}`),
    });
  };

  const toggleSelected = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const handleSelectConversation = async (id: string) => {
    setSidebarOpen(false);
    try {
      await chat.load(id);
    } catch (e) {
      toast("error", `Couldn't load chat: ${(e as Error).message}`);
    }
  };

  const handleDeleteConversation = async (id: string) => {
    try {
      await api.deleteConversation(id);
      if (id === chat.conversationId) chat.reset();
      qc.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      toast("error", `Delete failed: ${(e as Error).message}`);
    }
  };

  return (
    <div className="flex h-full overflow-hidden">
      {/* Sidebar: static on desktop, drawer on mobile */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 transition-transform md:static md:translate-x-0",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <Sidebar
          documents={documents}
          uploading={upload.isPending}
          onUpload={handleUpload}
          onDeleteDocument={handleDeleteDocument}
          onOpenDocument={(d) => setPdfTarget({ docId: d.id, filename: d.filename, page: 1, text: "" })}
          selected={new Set(activeFilter)}
          onToggleSelected={toggleSelected}
          onClearSelected={() => setSelected(new Set())}
          activeConversationId={chat.conversationId}
          onNewChat={() => {
            chat.reset();
            setSidebarOpen(false);
          }}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          health={health.data}
          healthError={health.isError}
        />
      </div>
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-zinc-200 px-3 py-2 md:hidden dark:border-zinc-800">
          <button onClick={() => setSidebarOpen(true)} aria-label="Open menu" className="rounded p-1">
            <Menu className="size-5" />
          </button>
          <span className="font-semibold">DocChat</span>
        </div>
        <HealthBanner health={health.data} error={health.error} />
        <ChatWindow
          messages={chat.messages}
          streaming={chat.streaming}
          hasReadyDocs={readyIds.size > 0}
          filterCount={activeFilter.length}
          onSend={(q) => chat.send(q, activeFilter)}
          onStop={chat.stop}
          onOpenSource={setPdfTarget}
        />
      </main>

      {pdfTarget && (
        <div className="fixed inset-0 z-40 flex bg-white lg:static lg:contents dark:bg-zinc-950">
          <Suspense fallback={null}>
            <PdfPanel target={pdfTarget} onClose={() => setPdfTarget(null)} />
          </Suspense>
        </div>
      )}

      <Toasts toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  );
}
