# EmberChat — AI Chatbot SaaS Dashboard

Next.js 15 (App Router) + TypeScript + Tailwind + ShadCN (new-york) + TanStack Query
frontend for the multi-tenant RAG chatbot API. Verified with `tsc --noEmit` (0 errors)
and a full `next build` (16 routes, middleware) — both green.

## Run
```bash
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE_URL -> FastAPI backend
npm run dev                        # http://localhost:3000  (proxies /api/v1/* to backend)
```

## Aesthetic
Refined editorial dashboard: warm paper canvas, a single "ember" accent (HSL 18 80% 48%),
Fraunces display + Manrope body + JetBrains Mono. Light/dark theme via CSS variables.
(Fonts load via `<link>` so builds never depend on a network fetch; swap to
`next/font/google` to self-host when you have network.)

## Folder structure
```
src/
  app/
    layout.tsx                 root: providers + fonts + Toaster
    page.tsx                   -> redirects to /dashboard
    globals.css                theme tokens (light/dark) + grain
    (auth)/                    split-screen auth shell
      login/ register/
    (dashboard)/               sidebar + topbar shell, wrapped in <AuthGuard>
      dashboard/ knowledge-base/ documents/ crawl/ chatbot/
      conversations/ leads/ analytics/ billing/ account/
  components/
    ui/                        ShadCN primitives (button, card, table, dialog, …)
    dashboard/                 sidebar, topbar, switchers, stat-card, empty-state, auth-guard
  hooks/                       TanStack Query hooks per resource
  lib/
    api/ (client.ts, types.ts) fetch client w/ token refresh + SSE; API types
    auth/storage.ts            token + active-tenant persistence
    utils.ts
  providers/                   query-provider, auth-provider
  middleware.ts                cookie-based first-paint route guard
```

## State management
- **Server state**: TanStack Query (per-resource hooks; auto-polling for in-flight
  document ingestion and crawl jobs).
- **Session/tenant state**: `AuthProvider` context — user, memberships, active company
  (+ permissions) and active chatbot, persisted to `localStorage`.

## Authentication
- Email/password against `/auth/*`. Access + refresh tokens in `localStorage`; a
  `cb_authed` cookie powers the middleware first-paint redirect.
- `lib/api/client.ts` attaches the Bearer token and **auto-refreshes once on 401**,
  retrying the request; on failure it clears tokens and redirects to `/login`.
- Guards: `middleware.ts` (cookie) + `<AuthGuard>` (context) — protected routes bounce
  guests to `/login`; authed users are bounced off `/login` and `/register`.

## API integration — what's live vs pending
Wired to real backend endpoints:
- **Auth / account**: login, register, refresh, logout, `/users/me`, `/companies`, `/companies/{id}/me`, `/companies/{id}/members`.
- **Chatbots**: list + create (+ public key / embed snippet).
- **Documents**: upload (multipart), list (auto-poll while processing), view chunks, delete, semantic search.
- **Website crawl**: start, list (auto-poll), progress, cancel.
- **Conversations**: list, create, history, and **streaming chat** (SSE) with rendered sources.

Backend tables exist but **endpoints are not built yet**, so these pages render an honest
"not yet available" state instead of fabricating data:
- **Leads** — empty state, ready to wire to `/leads`.
- **Billing** — illustrative plans, no payment provider connected.
- **Analytics** — figures are computed client-side from live documents/conversations/crawls;
  the chart and stats are real, with deeper time-series analytics flagged as pending.

Chatbot generation params (system prompt, temperature, top_k, max_tokens) live on the
backend model but aren't exposed by the create API, so the settings panel shows them as
managed defaults pending an update endpoint.
