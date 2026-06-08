"use client";
import { tokenStore } from "@/lib/auth/storage";
import type { ApiError, TokenPair } from "./types";

const PREFIX = "/api/v1";

export class ApiClientError extends Error {
  status: number;
  code: string;
  details?: unknown;
  constructor(status: number, body: ApiError | string) {
    const parsed = typeof body === "string" ? null : body;
    super(parsed?.error?.message || (typeof body === "string" ? body : "Request failed"));
    this.status = status;
    this.code = parsed?.error?.code || "error";
    this.details = parsed?.error?.details;
  }
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh = tokenStore.refresh;
  if (!refresh) return false;
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const res = await fetch(`${PREFIX}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        const data = (await res.json()) as TokenPair;
        tokenStore.set(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
  auth?: boolean; // default true
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, formData, signal, auth = true } = opts;

  const doFetch = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (auth && tokenStore.access) headers["Authorization"] = `Bearer ${tokenStore.access}`;
    let payload: BodyInit | undefined;
    if (formData) {
      payload = formData;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    return fetch(`${PREFIX}${path}`, { method, headers, body: payload, signal });
  };

  let res = await doFetch();
  if (res.status === 401 && auth && tokenStore.refresh) {
    if (await tryRefresh()) {
      res = await doFetch();
    } else {
      tokenStore.clear();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new ApiClientError(401, "Session expired");
    }
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const parsed = text ? JSON.parse(text) : undefined;
  if (!res.ok) throw new ApiClientError(res.status, parsed ?? text);
  return parsed as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown, opts?: Partial<RequestOptions>) =>
    request<T>(path, { method: "POST", body, ...opts }),
  postForm: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", formData }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  raw: request,
};

// Streaming helper for SSE chat responses.
export async function* streamChat(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<Record<string, unknown>> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (tokenStore.access) headers["Authorization"] = `Bearer ${tokenStore.access}`;
  const res = await fetch(`${PREFIX}${path}`, {
    method: "POST", headers, body: JSON.stringify(body), signal,
  });
  if (!res.ok || !res.body) throw new ApiClientError(res.status, await res.text());
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";
    for (const block of lines) {
      const line = block.trim();
      if (!line.startsWith("data:")) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return;
      try { yield JSON.parse(payload); } catch { /* ignore keep-alive */ }
    }
  }
}
