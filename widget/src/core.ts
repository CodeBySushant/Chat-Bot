/**
 * Embeddable AI chat widget.
 *
 * Loaded with a single script tag; reads its own data-* attributes, mounts an
 * isolated Shadow DOM UI, and talks to the public widget API:
 *   <script src="https://cdn.example.com/widget.js"
 *           data-key="pk_xxx" data-api="https://api.example.com"></script>
 *
 * No dependencies, no globals leaked, no host-page CSS collisions (Shadow DOM).
 */

// ----------------------------- types -----------------------------
interface WidgetConfig {
  chatbot_name: string;
  greeting: string;
  primary_color: string;
  position: string; // "bottom-right" | "bottom-left"
  suggested_prompts: string[];
  lead_capture: {
    enabled?: boolean;
    title?: string;
    fields?: string[]; // subset of ["name","email","phone"]
    trigger?: "after_first_message" | "button";
  };
  locale: string;
  launcher_icon_url: string | null;
  show_branding: boolean;
}

interface Msg {
  role: "user" | "assistant";
  content: string;
}

interface Settings {
  publicKey: string;
  apiBase: string;
  positionOverride: string | null;
  colorOverride: string | null;
}

// --------------------------- settings -----------------------------
function readSettings(): Settings | null {
  const el =
    (document.currentScript as HTMLScriptElement | null) ||
    (document.querySelector("script[data-key]") as HTMLScriptElement | null);
  if (!el) return null;
  const publicKey = el.getAttribute("data-key") || "";
  if (!publicKey) {
    console.warn("[chat-widget] missing data-key");
    return null;
  }
  let apiBase = el.getAttribute("data-api") || "";
  if (!apiBase) {
    try {
      apiBase = new URL(el.src).origin;
    } catch {
      apiBase = window.location.origin;
    }
  }
  return {
    publicKey,
    apiBase: apiBase.replace(/\/$/, ""),
    positionOverride: el.getAttribute("data-position"),
    colorOverride: el.getAttribute("data-primary-color"),
  };
}

// ------------------------- persistence ----------------------------
class Store {
  private key: string;
  conversationId: string | null = null;
  messages: Msg[] = [];

  constructor(publicKey: string) {
    this.key = `cbw:${publicKey}`;
    this.load();
  }
  private load() {
    try {
      const raw = localStorage.getItem(this.key);
      if (raw) {
        const data = JSON.parse(raw);
        this.conversationId = data.conversationId ?? null;
        this.messages = Array.isArray(data.messages) ? data.messages : [];
      }
    } catch {
      /* storage may be unavailable (private mode); run in-memory */
    }
  }
  save() {
    try {
      localStorage.setItem(
        this.key,
        JSON.stringify({
          conversationId: this.conversationId,
          messages: this.messages.slice(-50),
        }),
      );
    } catch {
      /* ignore */
    }
  }
  reset() {
    this.conversationId = null;
    this.messages = [];
    this.save();
  }
}

// --------------------------- API client ---------------------------
class WidgetApi {
  constructor(private base: string, private key: string) {}

  async config(): Promise<WidgetConfig> {
    const r = await fetch(`${this.base}/api/v1/widget/${this.key}/config`);
    if (!r.ok) throw new Error(`config ${r.status}`);
    return r.json();
  }

  async startConversation(visitorId: string): Promise<string> {
    const r = await fetch(`${this.base}/api/v1/widget/${this.key}/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ visitor_id: visitorId }),
    });
    if (!r.ok) throw new Error(`conversation ${r.status}`);
    return (await r.json()).conversation_id;
  }

  async *stream(
    conversationId: string,
    question: string,
    signal?: AbortSignal,
  ): AsyncGenerator<Record<string, unknown>> {
    const r = await fetch(
      `${this.base}/api/v1/widget/${this.key}/conversations/${conversationId}/messages/stream`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
        signal,
      },
    );
    if (!r.ok || !r.body) throw new Error(`stream ${r.status}`);
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() || "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (payload === "[DONE]") return;
        try {
          yield JSON.parse(payload);
        } catch {
          /* keep-alive */
        }
      }
    }
  }

  async captureLead(data: {
    name?: string;
    email?: string;
    phone?: string;
    conversation_id?: string | null;
  }): Promise<void> {
    await fetch(`${this.base}/api/v1/widget/${this.key}/leads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  }
}

export { readSettings, Store, WidgetApi };
export type { WidgetConfig, Msg, Settings };
