"use client";
// Analytics are derived client-side from live resources (documents, conversations,
// crawls). A dedicated analytics API (time-series, daily rollups) is a planned
// backend addition; until then these aggregates give a real, accurate snapshot.
import { useMemo } from "react";
import { useDocuments } from "./use-documents";
import { useConversations } from "./use-conversations";
import { useCrawls } from "./use-crawls";

export function useAnalytics() {
  const docs = useDocuments();
  const convs = useConversations();
  const crawls = useCrawls();

  const loading = docs.isLoading || convs.isLoading || crawls.isLoading;

  const stats = useMemo(() => {
    const d = docs.data ?? [];
    const c = convs.data ?? [];
    const cr = crawls.data ?? [];
    const ready = d.filter((x) => x.status === "ready").length;
    const chunks = d.reduce((s, x) => s + (x.chunk_count || 0), 0);
    const tokens = d.reduce((s, x) => s + (x.token_count || 0), 0);
    const messages = c.reduce((s, x) => s + (x.message_count || 0), 0);
    const pages = cr.reduce((s, x) => s + (x.pages_processed || 0), 0);

    const byStatus = ["ready", "processing", "pending", "failed"].map((status) => ({
      status,
      count: d.filter((x) => x.status === status).length,
    }));

    return {
      documents: d.length, readyDocuments: ready, chunks, tokens,
      conversations: c.length, messages, crawledPages: pages, byStatus,
    };
  }, [docs.data, convs.data, crawls.data]);

  return { stats, loading, backendPending: true };
}
