"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useAuth } from "@/providers/auth-provider";
import type { AnswerResponse, ChatMessage, Conversation } from "@/lib/api/types";

function base(c: string, b: string) { return `/companies/${c}/chatbots/${b}/conversations`; }

export function useConversations() {
  const { activeCompany, activeChatbot } = useAuth();
  return useQuery({
    queryKey: ["conversations", activeCompany, activeChatbot],
    enabled: !!activeCompany && !!activeChatbot,
    queryFn: () => api.get<Conversation[]>(base(activeCompany!, activeChatbot!)),
  });
}

export function useMessages(conversationId: string | null) {
  const { activeCompany, activeChatbot } = useAuth();
  return useQuery({
    queryKey: ["messages", conversationId],
    enabled: !!conversationId && !!activeCompany && !!activeChatbot,
    queryFn: () => api.get<ChatMessage[]>(`${base(activeCompany!, activeChatbot!)}/${conversationId}/messages`),
  });
}

export function useCreateConversation() {
  const { activeCompany, activeChatbot } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) =>
      api.post<Conversation>(base(activeCompany!, activeChatbot!), { channel: "playground", title: title ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["conversations", activeCompany, activeChatbot] }),
  });
}

export function useAsk(conversationId: string | null) {
  const { activeCompany, activeChatbot } = useAuth();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (question: string) =>
      api.post<AnswerResponse>(`${base(activeCompany!, activeChatbot!)}/${conversationId}/messages`, { question }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["messages", conversationId] });
      qc.invalidateQueries({ queryKey: ["conversations", activeCompany, activeChatbot] });
    },
  });
}

export function streamPath(company: string, bot: string, conversationId: string) {
  return `${base(company, bot)}/${conversationId}/messages/stream`;
}
