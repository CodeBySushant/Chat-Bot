"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import { activeStore, tokenStore } from "@/lib/auth/storage";
import type { Chatbot, MeResponse, MembershipSummary, RoleContext, TokenPair, User } from "@/lib/api/types";

type Status = "loading" | "authed" | "guest";

interface AuthState {
  status: Status;
  user: User | null;
  memberships: MembershipSummary[];
  activeCompany: string | null;
  activeChatbot: string | null;
  chatbots: Chatbot[];
  permissions: string[];
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  setActiveCompany: (id: string) => void;
  setActiveChatbot: (id: string) => void;
  refreshChatbots: () => Promise<void>;
  hasPermission: (code: string) => boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [memberships, setMemberships] = useState<MembershipSummary[]>([]);
  const [activeCompany, setActiveCompanyState] = useState<string | null>(null);
  const [activeChatbot, setActiveChatbotState] = useState<string | null>(null);
  const [chatbots, setChatbots] = useState<Chatbot[]>([]);
  const [permissions, setPermissions] = useState<string[]>([]);

  const loadCompanyScope = useCallback(async (companyId: string) => {
    activeStore.setCompany(companyId);
    setActiveCompanyState(companyId);
    try {
      const ctx = await api.get<RoleContext>(`/companies/${companyId}/me`);
      setPermissions(ctx.permissions);
    } catch {
      setPermissions([]);
    }
    try {
      const bots = await api.get<Chatbot[]>(`/companies/${companyId}/chatbots`);
      setChatbots(bots);
      const stored = activeStore.chatbot;
      const next = bots.find((b) => b.id === stored)?.id ?? bots[0]?.id ?? null;
      setActiveChatbotState(next);
      activeStore.setChatbot(next);
    } catch {
      setChatbots([]);
      setActiveChatbotState(null);
    }
  }, []);

  const bootstrap = useCallback(async () => {
    if (!tokenStore.access) { setStatus("guest"); return; }
    try {
      const me = await api.get<MeResponse>("/users/me");
      setUser(me.user);
      setMemberships(me.memberships);
      const stored = activeStore.company;
      const companyId =
        me.memberships.find((m) => m.company_id === stored)?.company_id ??
        me.memberships[0]?.company_id ??
        null;
      if (companyId) await loadCompanyScope(companyId);
      setStatus("authed");
    } catch {
      tokenStore.clear();
      setStatus("guest");
    }
  }, [loadCompanyScope]);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const login = useCallback(async (email: string, password: string) => {
    const tokens = await api.post<TokenPair>("/auth/login", { email, password }, { auth: false });
    tokenStore.set(tokens.access_token, tokens.refresh_token);
    await bootstrap();
    router.push("/dashboard");
  }, [bootstrap, router]);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    await api.post("/auth/register", { email, password, full_name: fullName ?? null }, { auth: false });
    await login(email, password);
  }, [login]);

  const logout = useCallback(async () => {
    try { if (tokenStore.refresh) await api.post("/auth/logout", { refresh_token: tokenStore.refresh }); } catch { /* ignore */ }
    tokenStore.clear();
    setUser(null); setMemberships([]); setPermissions([]); setChatbots([]);
    setActiveCompanyState(null); setActiveChatbotState(null);
    setStatus("guest");
    router.push("/login");
  }, [router]);

  const setActiveCompany = useCallback((id: string) => { loadCompanyScope(id); }, [loadCompanyScope]);
  const setActiveChatbot = useCallback((id: string) => { activeStore.setChatbot(id); setActiveChatbotState(id); }, []);
  const refreshChatbots = useCallback(async () => { if (activeCompany) await loadCompanyScope(activeCompany); }, [activeCompany, loadCompanyScope]);
  const hasPermission = useCallback((code: string) => permissions.includes(code), [permissions]);

  return (
    <Ctx.Provider value={{
      status, user, memberships, activeCompany, activeChatbot, chatbots, permissions,
      login, register, logout, setActiveCompany, setActiveChatbot, refreshChatbots, hasPermission,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
