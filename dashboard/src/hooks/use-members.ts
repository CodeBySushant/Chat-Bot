"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { useAuth } from "@/providers/auth-provider";
import type { Member } from "@/lib/api/types";

export function useMembers() {
  const { activeCompany } = useAuth();
  return useQuery({
    queryKey: ["members", activeCompany],
    enabled: !!activeCompany,
    queryFn: () => api.get<Member[]>(`/companies/${activeCompany}/members`),
  });
}
