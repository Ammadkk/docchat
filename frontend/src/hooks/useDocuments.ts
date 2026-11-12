import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type DocumentInfo } from "../api/client";

export function useDocuments(onStatusChange?: (doc: DocumentInfo) => void) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["documents"],
    queryFn: api.listDocuments,
    // Poll while anything is still being ingested.
    refetchInterval: (q) =>
      q.state.data?.some((d) => d.status === "processing") ? 1500 : false,
  });

  // Fire a callback when a document finishes processing (for toasts).
  const previous = useRef<Map<string, string>>(new Map());
  useEffect(() => {
    for (const doc of query.data ?? []) {
      const before = previous.current.get(doc.id);
      if (before === "processing" && doc.status !== "processing") onStatusChange?.(doc);
      previous.current.set(doc.id, doc.status);
    }
  }, [query.data, onStatusChange]);

  const upload = useMutation({
    mutationFn: api.uploadDocuments,
    onSuccess: (docs) => {
      docs.forEach((d) => previous.current.set(d.id, d.status));
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const remove = useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  return { ...query, documents: query.data ?? [], upload, remove };
}
