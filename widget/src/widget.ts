import { readSettings, Store, WidgetApi } from "./core";
import type { Msg, Settings, WidgetConfig } from "./core";

// SVG icons (inline, no external requests)
const ICON_CHAT =
  '<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>';
const ICON_CLOSE =
  '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
const ICON_SEND =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>';

function visitorId(): string {
  const k = "cbw:visitor";
  try {
    let v = localStorage.getItem(k);
    if (!v) {
      v = "v_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(k, v);
    }
    return v;
  } catch {
    return "v_anon";
  }
}

function styles(color: string, side: "left" | "right"): string {
  return `
  :host { all: initial; }
  *, *::before, *::after { box-sizing: border-box; }
  .cbw-root {
    --cbw-primary: ${color};
    --cbw-radius: 16px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #1c1917;
  }
  .cbw-launcher {
    position: fixed; bottom: 20px; ${side}: 20px; z-index: 2147483000;
    width: 58px; height: 58px; border-radius: 50%; border: none; cursor: pointer;
    background: var(--cbw-primary); color: #fff; display: flex; align-items: center; justify-content: center;
    box-shadow: 0 6px 24px rgba(0,0,0,.22); transition: transform .15s ease, box-shadow .15s ease;
  }
  .cbw-launcher:hover { transform: translateY(-2px) scale(1.04); }
  .cbw-launcher:focus-visible { outline: 3px solid color-mix(in srgb, var(--cbw-primary) 50%, white); }
  .cbw-panel {
    position: fixed; bottom: 90px; ${side}: 20px; z-index: 2147483000;
    width: 380px; max-width: calc(100vw - 32px); height: 600px; max-height: calc(100vh - 120px);
    background: #fff; border-radius: var(--cbw-radius); box-shadow: 0 12px 48px rgba(0,0,0,.28);
    display: flex; flex-direction: column; overflow: hidden; opacity: 0; transform: translateY(12px) scale(.98);
    transition: opacity .18s ease, transform .18s ease; pointer-events: none;
  }
  .cbw-panel.open { opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }
  .cbw-header { background: var(--cbw-primary); color: #fff; padding: 16px 18px; display: flex; align-items: center; justify-content: space-between; }
  .cbw-title { font-weight: 650; font-size: 15px; }
  .cbw-sub { font-size: 12px; opacity: .85; margin-top: 2px; }
  .cbw-iconbtn { background: rgba(255,255,255,.16); border: none; color: #fff; cursor: pointer; width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; }
  .cbw-iconbtn:hover { background: rgba(255,255,255,.28); }
  .cbw-body { flex: 1; overflow-y: auto; padding: 16px; background: #faf9f7; display: flex; flex-direction: column; gap: 10px; }
  .cbw-msg { max-width: 82%; padding: 10px 13px; border-radius: 14px; font-size: 14px; line-height: 1.45; white-space: pre-wrap; word-wrap: break-word; }
  .cbw-msg.user { align-self: flex-end; background: var(--cbw-primary); color: #fff; border-bottom-right-radius: 4px; }
  .cbw-msg.assistant { align-self: flex-start; background: #fff; border: 1px solid #ece9e4; border-bottom-left-radius: 4px; }
  .cbw-sources { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 4px; }
  .cbw-chip { font-size: 10px; background: #f0ede8; color: #78716c; border-radius: 6px; padding: 2px 6px; }
  .cbw-typing { align-self: flex-start; background: #fff; border: 1px solid #ece9e4; border-radius: 14px; padding: 12px 14px; display: flex; gap: 4px; }
  .cbw-dot { width: 7px; height: 7px; border-radius: 50%; background: #c7c2bb; animation: cbw-bounce 1.2s infinite; }
  .cbw-dot:nth-child(2) { animation-delay: .2s; } .cbw-dot:nth-child(3) { animation-delay: .4s; }
  @keyframes cbw-bounce { 0%,60%,100% { transform: translateY(0); opacity:.6 } 30% { transform: translateY(-5px); opacity:1 } }
  .cbw-prompts { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
  .cbw-prompt { text-align: left; background: #fff; border: 1px solid #e7e3dd; border-radius: 12px; padding: 9px 12px; font-size: 13px; cursor: pointer; color: #44403c; }
  .cbw-prompt:hover { border-color: var(--cbw-primary); color: var(--cbw-primary); }
  .cbw-footer { border-top: 1px solid #eee; padding: 10px; background: #fff; }
  .cbw-inputrow { display: flex; gap: 8px; align-items: flex-end; }
  .cbw-input { flex: 1; resize: none; border: 1px solid #e0dcd5; border-radius: 12px; padding: 10px 12px; font-size: 14px; font-family: inherit; max-height: 120px; outline: none; }
  .cbw-input:focus { border-color: var(--cbw-primary); }
  .cbw-send { background: var(--cbw-primary); color: #fff; border: none; border-radius: 12px; width: 40px; height: 40px; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
  .cbw-send:disabled { opacity: .5; cursor: not-allowed; }
  .cbw-branding { text-align: center; font-size: 11px; color: #a8a29e; padding: 6px; background: #fff; }
  .cbw-branding a { color: #78716c; text-decoration: none; }
  .cbw-lead { background: #fff; border: 1px solid #ece9e4; border-radius: 14px; padding: 14px; display: flex; flex-direction: column; gap: 8px; }
  .cbw-lead h4 { margin: 0 0 2px; font-size: 14px; }
  .cbw-lead input { border: 1px solid #e0dcd5; border-radius: 10px; padding: 9px 11px; font-size: 13px; font-family: inherit; outline: none; }
  .cbw-lead input:focus { border-color: var(--cbw-primary); }
  .cbw-lead button { background: var(--cbw-primary); color: #fff; border: none; border-radius: 10px; padding: 9px; font-size: 13px; font-weight: 600; cursor: pointer; }
  @media (max-width: 480px) {
    .cbw-panel { bottom: 0; ${side}: 0; right: 0; left: 0; width: 100vw; max-width: 100vw; height: 100dvh; max-height: 100dvh; border-radius: 0; }
    .cbw-launcher { bottom: 16px; ${side}: 16px; }
  }`;
}

class WidgetUI {
  private cfg: WidgetConfig;
  private api: WidgetApi;
  private store: Store;
  private settings: Settings;
  private root!: ShadowRoot;
  private panel!: HTMLElement;
  private body!: HTMLElement;
  private input!: HTMLTextAreaElement;
  private sendBtn!: HTMLButtonElement;
  private open = false;
  private busy = false;
  private leadShown = false;

  constructor(cfg: WidgetConfig, api: WidgetApi, store: Store, settings: Settings) {
    this.cfg = cfg;
    this.api = api;
    this.store = store;
    this.settings = settings;
  }

  mount() {
    const host = document.createElement("div");
    host.id = "chatbot-widget-host";
    document.body.appendChild(host);
    this.root = host.attachShadow({ mode: "open" });

    const side = (this.settings.positionOverride || this.cfg.position).includes("left")
      ? "left"
      : "right";
    const color = this.settings.colorOverride || this.cfg.primary_color || "#e8590c";

    const style = document.createElement("style");
    style.textContent = styles(color, side as "left" | "right");
    this.root.appendChild(style);

    const wrap = document.createElement("div");
    wrap.className = "cbw-root";
    wrap.innerHTML = `
      <button class="cbw-launcher" aria-label="Open chat">${ICON_CHAT}</button>
      <div class="cbw-panel" role="dialog" aria-label="Chat window">
        <div class="cbw-header">
          <div>
            <div class="cbw-title">${escapeHtml(this.cfg.chatbot_name)}</div>
            <div class="cbw-sub">Typically replies instantly</div>
          </div>
          <button class="cbw-iconbtn cbw-close" aria-label="Close chat">${ICON_CLOSE}</button>
        </div>
        <div class="cbw-body"></div>
        <div class="cbw-footer">
          <div class="cbw-inputrow">
            <textarea class="cbw-input" rows="1" placeholder="Type your message…" aria-label="Message"></textarea>
            <button class="cbw-send" aria-label="Send">${ICON_SEND}</button>
          </div>
        </div>
        ${this.cfg.show_branding ? '<div class="cbw-branding">Powered by <a href="#" target="_blank" rel="noopener">EmberChat</a></div>' : ""}
      </div>`;
    this.root.appendChild(wrap);

    this.panel = this.root.querySelector(".cbw-panel")!;
    this.body = this.root.querySelector(".cbw-body")!;
    this.input = this.root.querySelector(".cbw-input")!;
    this.sendBtn = this.root.querySelector(".cbw-send")!;

    this.root.querySelector(".cbw-launcher")!.addEventListener("click", () => this.toggle());
    this.root.querySelector(".cbw-close")!.addEventListener("click", () => this.toggle(false));
    this.sendBtn.addEventListener("click", () => this.send());
    this.input.addEventListener("keydown", (e) => {
      if ((e as KeyboardEvent).key === "Enter" && !(e as KeyboardEvent).shiftKey) {
        e.preventDefault();
        this.send();
      }
    });
    this.input.addEventListener("input", () => this.autosize());
    document.addEventListener("keydown", (e) => {
      if ((e as KeyboardEvent).key === "Escape" && this.open) this.toggle(false);
    });

    this.renderHistory();
  }

  private autosize() {
    this.input.style.height = "auto";
    this.input.style.height = Math.min(this.input.scrollHeight, 120) + "px";
  }

  private toggle(force?: boolean) {
    this.open = force ?? !this.open;
    this.panel.classList.toggle("open", this.open);
    if (this.open) {
      this.input.focus();
      this.scrollDown();
    }
  }

  private renderHistory() {
    this.body.innerHTML = "";
    if (this.store.messages.length === 0) {
      this.addBubble("assistant", this.cfg.greeting);
      if (this.cfg.suggested_prompts?.length) this.renderPrompts();
    } else {
      for (const m of this.store.messages) this.addBubble(m.role, m.content, false);
    }
    this.scrollDown();
  }

  private renderPrompts() {
    const box = document.createElement("div");
    box.className = "cbw-prompts";
    for (const p of this.cfg.suggested_prompts.slice(0, 4)) {
      const b = document.createElement("button");
      b.className = "cbw-prompt";
      b.textContent = p;
      b.addEventListener("click", () => {
        box.remove();
        this.input.value = p;
        this.send();
      });
      box.appendChild(b);
    }
    this.body.appendChild(box);
  }

  private addBubble(role: Msg["role"], text: string, persist = true): HTMLElement {
    const el = document.createElement("div");
    el.className = `cbw-msg ${role}`;
    el.textContent = text;
    this.body.appendChild(el);
    this.scrollDown();
    if (persist) {
      this.store.messages.push({ role, content: text });
      this.store.save();
    }
    return el;
  }

  private showTyping(): HTMLElement {
    const t = document.createElement("div");
    t.className = "cbw-typing";
    t.innerHTML = '<span class="cbw-dot"></span><span class="cbw-dot"></span><span class="cbw-dot"></span>';
    this.body.appendChild(t);
    this.scrollDown();
    return t;
  }

  private scrollDown() {
    requestAnimationFrame(() => (this.body.scrollTop = this.body.scrollHeight));
  }

  private async ensureConversation(): Promise<string> {
    if (this.store.conversationId) return this.store.conversationId;
    const id = await this.api.startConversation(visitorId());
    this.store.conversationId = id;
    this.store.save();
    return id;
  }

  private async send() {
    const text = this.input.value.trim();
    if (!text || this.busy) return;
    this.input.value = "";
    this.autosize();
    this.root.querySelector(".cbw-prompts")?.remove();
    this.addBubble("user", text);
    this.busy = true;
    this.sendBtn.disabled = true;
    const typing = this.showTyping();

    try {
      const convId = await this.ensureConversation();
      let assistantEl: HTMLElement | null = null;
      let acc = "";
      let sources: Array<{ title?: string | null; page_number?: number | null }> = [];

      for await (const ev of this.api.stream(convId, text)) {
        if (ev.type === "delta") {
          if (!assistantEl) {
            typing.remove();
            assistantEl = this.addBubble("assistant", "", false);
          }
          acc += ev.text as string;
          assistantEl.textContent = acc;
          this.scrollDown();
        } else if (ev.type === "done") {
          sources = (ev.sources as typeof sources) || [];
        } else if (ev.type === "error") {
          if (!assistantEl) {
            typing.remove();
            assistantEl = this.addBubble("assistant", "", false);
          }
          acc = "Sorry, something went wrong. Please try again.";
          assistantEl.textContent = acc;
        }
      }
      if (!assistantEl) {
        typing.remove();
        assistantEl = this.addBubble("assistant", "I couldn't generate a response.", false);
        acc = assistantEl.textContent || "";
      }
      if (sources.length && assistantEl) this.renderSources(assistantEl, sources);

      // persist final assistant turn
      this.store.messages.push({ role: "assistant", content: acc });
      this.store.save();

      this.maybeShowLead();
    } catch {
      typing.remove();
      this.addBubble("assistant", "I'm having trouble connecting. Please try again later.", false);
    } finally {
      this.busy = false;
      this.sendBtn.disabled = false;
      this.input.focus();
    }
  }

  private renderSources(
    after: HTMLElement,
    sources: Array<{ title?: string | null; page_number?: number | null }>,
  ) {
    const box = document.createElement("div");
    box.className = "cbw-sources";
    const seen = new Set<string>();
    for (const s of sources.slice(0, 4)) {
      const label = (s.title || "source") + (s.page_number ? ` p.${s.page_number}` : "");
      if (seen.has(label)) continue;
      seen.add(label);
      const chip = document.createElement("span");
      chip.className = "cbw-chip";
      chip.textContent = label;
      box.appendChild(chip);
    }
    if (box.childNodes.length) after.appendChild(box);
  }

  private maybeShowLead() {
    const lc = this.cfg.lead_capture || {};
    if (!lc.enabled || this.leadShown) return;
    if ((lc.trigger || "after_first_message") !== "after_first_message") return;
    this.leadShown = true;

    const fields = lc.fields?.length ? lc.fields : ["name", "email"];
    const form = document.createElement("div");
    form.className = "cbw-lead";
    form.innerHTML = `<h4>${escapeHtml(lc.title || "Want us to follow up?")}</h4>`;
    const inputs: Record<string, HTMLInputElement> = {};
    for (const f of fields) {
      const i = document.createElement("input");
      i.type = f === "email" ? "email" : f === "phone" ? "tel" : "text";
      i.placeholder = f.charAt(0).toUpperCase() + f.slice(1);
      form.appendChild(i);
      inputs[f] = i;
    }
    const btn = document.createElement("button");
    btn.textContent = "Submit";
    btn.addEventListener("click", async () => {
      const payload: Record<string, string> = {};
      for (const f of fields) if (inputs[f].value.trim()) payload[f] = inputs[f].value.trim();
      if (!Object.keys(payload).length) return;
      btn.disabled = true;
      btn.textContent = "Sending…";
      try {
        await this.api.captureLead({ ...payload, conversation_id: this.store.conversationId });
        form.innerHTML = "<h4>Thanks! We'll be in touch.</h4>";
      } catch {
        btn.disabled = false;
        btn.textContent = "Try again";
      }
    });
    form.appendChild(btn);
    this.body.appendChild(form);
    this.scrollDown();
  }
}

function escapeHtml(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ----------------------------- bootstrap -----------------------------
async function init() {
  const settings = readSettings();
  if (!settings) return;
  const api = new WidgetApi(settings.apiBase, settings.publicKey);
  try {
    const cfg = await api.config();
    const store = new Store(settings.publicKey);
    const ui = new WidgetUI(cfg, api, store, settings);
    if (document.body) ui.mount();
    else window.addEventListener("DOMContentLoaded", () => ui.mount());
  } catch (e) {
    console.warn("[chat-widget] failed to initialize:", e);
  }
}

init();
