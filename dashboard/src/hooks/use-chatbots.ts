"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useAuth } from "@/providers/auth-provider";
import type { Chatbot } from "@/lib/api/types";

export function useChatbots() {
  const { activeCompany } = useAuth();
  return useQuery({
    queryKey: ["chatbots", activeCompany],
    enabled: !!activeCompany,
    queryFn: () => api.get<Chatbot[]>(`/companies/${activeCompany}/chatbots`),
  });
}

export function useCreateChatbot() {
  const { activeCompany, refreshChatbots } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; slug: string }) =>
      api.post<Chatbot>(`/companies/${activeCompany}/chatbots`, body),
    onSuccess: async () => {
      await refreshChatbots();
      qc.invalidateQueries({ queryKey: ["chatbots", activeCompany] });
    },
  });
}
