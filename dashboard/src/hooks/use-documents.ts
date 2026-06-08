"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useAuth } from "@/providers/auth-provider";
import type { Document, DocumentChunk } from "@/lib/api/types";

function base(company: string, bot: string) {
  return `/companies/${company}/chatbots/${bot}/documents`;
}

export function useDocuments() {
  const { activeCompany, activeChatbot } = useAuth();
  return useQuery({
    queryKey: ["documents", activeCompany, activeChatbot],
    enabled: !!activeCompany && !!activeChatbot,
    refetchInterval: (q) => {
      const data = q.state.data as Document[] | undefined;
      return data?.some((d) => d.status === "pending" || d.status === "processing") ? 2000 : false;
    },
    queryFn: () => api.get<Document[]>(base(activeCompany!, activeChatbot!)),
  });
}

export function useUploadDocument() {
  const { activeCompany, activeChatbot } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append("file", file);
      return api.postForm<Document>(base(activeCompany!, activeChatbot!), fd);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", activeCompany, activeChatbot] }),
  });
}

export function useDeleteDocument() {
  const { activeCompany, activeChatbot } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`${base(activeCompany!, activeChatbot!)}/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents", activeCompany, activeChatbot] }),
  });
}

export function useDocumentChunks(id: string | null) {
  const { activeCompany, activeChatbot } = useAuth();
  return useQuery({
    queryKey: ["chunks", id],
    enabled: !!id && !!activeCompany && !!activeChatbot,
    queryFn: () => api.get<DocumentChunk[]>(`${base(activeCompany!, activeChatbot!)}/${id}/chunks`),
  });
}

export interface SearchResult { score: number; chunk_id: string | null; document_id: string | null; chunk_index: number | null; text: string | null; }
export function useSearch() {
  const { activeCompany, activeChatbot } = useAuth();
  return useMutation({
    mutationFn: (query: string) =>
      api.post<{ query: string; results: SearchResult[] }>(`${base(activeCompany!, activeChatbot!)}/search`, { query, top_k: 5 }),
  });
}
