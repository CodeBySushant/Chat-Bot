# Embeddable AI Chat Widget

A production-ready chat widget that drops into **any website with one script tag**
and talks to the public widget API (key-authenticated, no user login).

```html
<script
  src="https://cdn.yourhost.com/widget.js"
  data-key="pk_your_chatbot_public_key"
  data-api="https://api.yourhost.com"></script>
```

That's the entire integration. `data-api` is optional (defaults to the origin the
script was served from). Optional overrides: `data-position="bottom-left"`,
`data-primary-color="#0ea5e9"`.

## Why it works on any site
- **Shadow DOM isolation** — all markup and CSS live inside a shadow root, so the
  host page's styles never bleed in and the widget never restyles the host.
- **No dependencies, no globals** — compiled to a single ~15 KB minified IIFE
  (`(()=>{…})()`); nothing is attached to `window`.
- **Self-initializing** — reads its own `<script>` tag via `document.currentScript`.
- **Permissive CORS + per-chatbot domain allowlist** — callable cross-origin, but
  the API rejects embedding from domains outside the chatbot's allowlist.

## Features
- Floating launcher button (corner configurable, mobile-aware).
- Chat window with smooth open/close, ESC to close.
- **Mobile responsive** — becomes a full-screen sheet under 480px (`100dvh`).
- **Typing indicator** while the assistant is thinking.
- **Streaming messages** — token-by-token via the SSE endpoint (`fetch` + `ReadableStream`).
- **Conversation persistence** — `conversation_id` + transcript saved to
  `localStorage` (keyed by public key); restored on reload. Degrades to in-memory
  in private mode.
- **Theme customization** — primary color from server config or `data-primary-color`.
- **Branding customization** — chatbot name, greeting, launcher icon, suggested
  prompts, "Powered by" toggle — all from server config.
- **Lead capture** — configurable form (name/email/phone) posted to the leads API.
- Source chips rendered under grounded answers.
- XSS-safe rendering (text set via `textContent`, never `innerHTML` for messages).

## Architecture
```
src/
  core.ts     readSettings() (script-tag data-*), Store (localStorage persistence),
              WidgetApi (config / startConversation / stream / captureLead)
  widget.ts   WidgetUI (Shadow DOM, launcher, panel, streaming render, typing,
              suggested prompts, lead form, mobile CSS) + auto-init bootstrap
dist/
  widget.js       minified IIFE bundle (the only file you deploy)
  widget.js.map   source map
```

Lifecycle: script loads → read `data-key`/`data-api` → `GET /widget/{key}/config`
→ mount launcher → on first message, `POST /widget/{key}/conversations` → stream
answers from `POST /widget/{key}/conversations/{id}/messages/stream` → optional
`POST /widget/{key}/leads`.

## Build process
```bash
npm install
npm run build      # esbuild --bundle --minify --format=iife --target=es2018 -> dist/widget.js (+ .map)
npm run build:dev  # unminified, for debugging
npm run watch      # rebuild on change
npx tsc --noEmit   # type check
```
Deploy `dist/widget.js` to any static host/CDN. Verified: `tsc` clean, bundle
parses as valid JS, ~15 KB.

## API integration (public surface)
All endpoints resolve the chatbot from its `public_key` and enforce the domain
allowlist via `Origin`/`Referer`. No user JWT involved.
- `GET  /api/v1/widget/{key}/config`
- `POST /api/v1/widget/{key}/conversations`
- `POST /api/v1/widget/{key}/conversations/{id}/messages/stream`  (SSE)
- `POST /api/v1/widget/{key}/leads`

A chatbot must be **published** (`status = active`) for the widget to load.

## Local demo
Serve `dist/widget.js` and `demo.html` from the same folder, set a real public key
in `demo.html`, and run the backend on `:8000`:
```bash
( cd dist && cp ../demo.html . && python3 -m http.server 5500 )
# open http://127.0.0.1:5500/demo.html
```
