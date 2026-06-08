"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useAuth } from "@/providers/auth-provider";
import type { CrawlJob } from "@/lib/api/types";

function base(c: string, b: string) { return `/companies/${c}/chatbots/${b}/crawls`; }

export function useCrawls() {
  const { activeCompany, activeChatbot } = useAuth();
  return useQuery({
    queryKey: ["crawls", activeCompany, activeChatbot],
    enabled: !!activeCompany && !!activeChatbot,
    refetchInterval: (q) => {
      const data = q.state.data as CrawlJob[] | undefined;
      return data?.some((j) => j.status === "queued" || j.status === "running") ? 2000 : false;
    },
    queryFn: () => api.get<CrawlJob[]>(base(activeCompany!, activeChatbot!)),
  });
}

export interface CrawlInput { start_url: string; mode: string; max_pages: number; max_depth: number; }
export function useStartCrawl() {
  const { activeCompany, activeChatbot } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CrawlInput) => api.post<CrawlJob>(base(activeCompany!, activeChatbot!), body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crawls", activeCompany, activeChatbot] }),
  });
}

export function useCancelCrawl() {
  const { activeCompany, activeChatbot } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.post<CrawlJob>(`${base(activeCompany!, activeChatbot!)}/${jobId}/cancel`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["crawls", activeCompany, activeChatbot] }),
  });
}
