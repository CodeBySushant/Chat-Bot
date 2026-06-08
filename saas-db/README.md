# Chatbot SaaS — Auth & Multi-Tenant Foundation

Production-shaped FastAPI foundation for the multi-tenant chatbot platform:
JWT auth, revocable refresh tokens, registration, login, password reset, email
verification, RBAC, company creation & membership, and Postgres-RLS tenant
isolation. Built on the existing SQLAlchemy 2.0 models and Alembic migrations,
and verified end-to-end against live PostgreSQL 16 (33/33 checks, deterministic).

## Architecture

```
app/
  main.py                  # app factory: CORS, middleware, handlers, routes, lifespan
  core/
    config.py              # pydantic-settings (env / .env); cached get_settings()
    logging.py             # correlation-id logging (request_id contextvar)
    security.py            # bcrypt hashing, JWT encode/decode, opaque-token gen
    exceptions.py          # AppError hierarchy + JSON error envelope handlers
  db/
    base.py                # DeclarativeBase, naming convention, mixins
    enums.py               # PG enums (incl. TokenPurpose)
    session.py             # dual async engines (app_rw RLS / app_admin BYPASSRLS)
  models/                  # SQLAlchemy models (tenancy, auth, bots, chat, ...)
    auth.py                # UserSession (refresh tokens), VerificationToken
  schemas/__init__.py      # pydantic v2 request/response models
  services/
    auth_service.py        # register, authenticate, token issue/rotate, reset, verify
    company_service.py     # company creation, membership, permission loading
  api/
    deps.py                # DI: sessions, current user, tenant context, permissions
    v1/
      auth.py              # /auth/*
      users.py             # /users/me
      companies.py         # /companies/*
  middleware/context.py    # request id + access logging
alembic/versions/          # 0001 schema, 0002 RBAC seed, 0003 auth tables
```

## Security model

- **Access token** — stateless JWT (HS256), 15 min TTL, carries `sub`, `jti`, `type`.
- **Refresh token** — opaque random string; only its SHA-256 hash is stored in
  `user_sessions`. Rotated on every refresh (old token revoked); revocable on
  logout; all sessions revoked on password reset.
- **Password hashing** — bcrypt with a SHA-256 pre-hash for inputs over 72 bytes.
- **Tenant isolation** — two DB roles. `app_rw` is subject to PostgreSQL RLS;
  `app_admin` (BYPASSRLS) is used only for bootstrap (registration lookups,
  company creation, "list my companies"). The tenant dependency sets
  `app.current_company` via `set_config(..., true)` (transaction-local), and the
  membership lookup under RLS *is* the authorization gate — supplying an
  arbitrary company id grants nothing without a real membership row.
- **RBAC** — system roles (owner/admin/member/viewer) map to a permission
  catalog via `role_permissions`; `require_permission("code")` guards endpoints.

## Transaction discipline

Writes commit **inside the service call**, before the handler returns, rather
than in dependency teardown — teardown runs after the response is dispatched and
caused read-after-write races (a logout followed immediately by a refresh, etc.).
Dependencies now only roll back on error and close the session.

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET  | `/health` | — | liveness |
| POST | `/api/v1/auth/register` | — | 201; 409 on duplicate |
| POST | `/api/v1/auth/login` | — | returns access + refresh |
| POST | `/api/v1/auth/refresh` | — | rotates refresh token |
| POST | `/api/v1/auth/logout` | — | 204; revokes refresh token |
| POST | `/api/v1/auth/password-reset/request` | — | 202; dev token in non-prod |
| POST | `/api/v1/auth/password-reset/confirm` | — | 204; revokes all sessions |
| POST | `/api/v1/auth/verify-email/request` | — | 202; dev token in non-prod |
| POST | `/api/v1/auth/verify-email/confirm` | — | 204 |
| GET  | `/api/v1/users/me` | Bearer | profile + memberships |
| POST | `/api/v1/companies` | Bearer | create company (caller becomes owner) |
| GET  | `/api/v1/companies` | Bearer | list my companies |
| GET  | `/api/v1/companies/{id}/me` | Bearer | my role + permissions |
| GET  | `/api/v1/companies/{id}/members` | Bearer + `members:invite` | list members |
| POST | `/api/v1/companies/{id}/members` | Bearer + `members:invite` | add member |

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env            # set JWT_SECRET_KEY and DB URLs
alembic upgrade head            # 0001 schema -> 0002 RBAC -> 0003 auth tables
uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

`.env` expects two DSNs: `DATABASE_URL` (role `app_rw`, RLS) and
`DATABASE_ADMIN_URL` (role `app_admin`, BYPASSRLS).

## Verification

`tests/e2e.py` exercises every endpoint plus the security boundaries:
registration/duplicate, login/bad-password, auth guards, company creation,
membership, **cross-tenant isolation** (non-member → 403), **RBAC**
(member role lacks `members:invite` → 403), **refresh rotation** (reused old
token → 401), password reset (old password rejected, token single-use), email
verification, and logout (refresh after logout → 401). Result: **33/33**,
deterministic across repeated runs.

## Scope

This foundation implements the auth/tenant slice on the **v1** schema (plus the
`user_sessions` / `verification_tokens` auth tables). The v2 blueprint changes
(composite tenant FKs, billing/metering hardening, outbox, partitioning of
conversations) are deliberately out of scope here and tracked for the
consolidated baseline.

---

# Website Crawling System

Crawls a site (or its sitemap), extracts clean main content, and feeds unique
pages into the tenant knowledge base via the existing ingestion pipeline.
Verified end-to-end (22/22) against a local test site.

## Pipeline
```
Start crawl → fetch (retry/backoff) → robots check → extract main content
  (strip script/style/nav/header/footer/aside) → dedupe by content hash
  → store as Document → enqueue ingestion (chunk → embed → Qdrant)
```

## Modes
- **crawl** — breadth-first from a start URL, discovering internal links up to `max_depth`/`max_pages`, scoped to the same site (subdomains allowed).
- **sitemap** — fetch and parse `sitemap.xml` (handles sitemap-index recursion); ingest listed pages, no link discovery.

## Components (`app/services/crawler/`, `app/workers/`)
- `fetcher.py` — async httpx GET with exponential-backoff **retries** on timeouts/transport errors/429/5xx, content-type guard, per-page size cap.
- `url_utils.py` — URL normalization (resolve relative, drop fragments/default ports/trailing slash, skip binary assets) + same-site scoping.
- `html_extract.py` — link discovery + **boilerplate removal** (tags: script/style/nav/header/footer/aside/form/iframe/svg + id/class/role heuristics) and main-content extraction (`<main>`/`<article>`/`[role=main]`).
- `sitemap.py` — sitemap + sitemap-index parsing (namespace-agnostic).
- `engine.py` — orchestration: robots.txt enforcement, BFS levels with bounded concurrency, **content-hash dedup** (within crawl + against existing chatbot documents), per-level counter/status persistence, **cancellation** between levels, store-and-enqueue, retry/error handling, terminal status.
- `crawl_service.py` — job create/list/get/cancel; one active crawl per (chatbot, URL).
- `workers/crawl_worker.py` — background crawl worker pool (separate queue from ingestion), started in the app lifespan.

## Endpoints (tenant + permission scoped)
```
POST   /companies/{cid}/chatbots/{bid}/crawls            documents:create   ({start_url, mode, max_pages, max_depth, same_domain_only})
GET    /companies/{cid}/chatbots/{bid}/crawls            documents:read
GET    /companies/{cid}/chatbots/{bid}/crawls/{job_id}   documents:read     (status + counters)
POST   /companies/{cid}/chatbots/{bid}/crawls/{job_id}/cancel  documents:create
```
Crawled pages become `Document`s (`source_type=crawl`, `crawler_job_id` set) and
appear via the existing documents/search endpoints once ingested.

## Config
`CRAWL_WORKERS`, `CRAWLER_USER_AGENT`, `CRAWLER_MAX_PAGES`, `CRAWLER_MAX_DEPTH`,
`CRAWLER_CONCURRENCY`, `CRAWLER_TIMEOUT_SECONDS`, `CRAWLER_RETRY_MAX`,
`CRAWLER_RESPECT_ROBOTS`. See `.env.example`.

## Production note
Like ingestion, the crawl queue is in-process (`asyncio`); for multi-process
deployments swap `workers/crawl_worker.py` for a durable broker. Crawled-page
dedup uses the same `content_hash` mechanism, so re-crawls don't duplicate
documents.

---

# Unified AI Provider Layer

Provider-agnostic chat/LLM access. Switching backends is a single env-var change:

```
AI_PROVIDER=ollama     # local Ollama runtime  (default)
AI_PROVIDER=openai     # OpenAI / OpenAI-compatible API
```

Verified end-to-end (19/19) against a fake server speaking both wire protocols
(non-streaming + streaming + error statuses).

## Interface (`app/services/ai/`)
- `base.py` — `ChatProvider` ABC with `complete()` (full result) and `stream()`
  (async iterator of text deltas); shared `ChatMessage`, `CompletionResult`, `Usage`.
  Messages accepted as `ChatMessage`, dict, or `(role, content)`.
- `errors.py` — common taxonomy: `AIConfigError`, `AIAuthError`, `AIRateLimitError`,
  `AITimeoutError`, `AIConnectionError`, `AIResponseError` (all `AIProviderError`).
  Providers map transport/HTTP failures into these, so callers handle errors
  identically regardless of backend.
- `openai_provider.py` — OpenAI-compatible `/chat/completions`; SSE streaming
  (`data: …`/`[DONE]`); Bearer auth; usage + finish_reason parsed.
- `ollama_provider.py` — Ollama `/api/chat`; NDJSON streaming (`done` sentinel);
  maps `prompt_eval_count`/`eval_count` to usage.
- `factory.py` — registry + `get_chat_provider()` (env-driven, cached). New
  providers are added via `register_provider(name, builder)` without touching
  existing code. `close_providers()` is called on app shutdown.

## Usage
```python
from app.services.ai import get_chat_provider, ChatMessage

provider = get_chat_provider()                      # honors AI_PROVIDER
result = await provider.complete([ChatMessage("user", "Hello")])
print(result.text, result.usage)

async for delta in provider.stream([ChatMessage("user", "Hi")]):
    print(delta, end="")
```

## Adding a future provider
```python
from app.services.ai import register_provider
from app.services.ai.base import ChatProvider
class MyProvider(ChatProvider):
    name = "myllm"
    async def complete(self, messages, **kw): ...
    async def stream(self, messages, **kw): ...
register_provider("myllm", lambda: MyProvider(...))
# then AI_PROVIDER=myllm
```

## Config
`AI_PROVIDER`, `AI_REQUEST_TIMEOUT`, `AI_DEFAULT_TEMPERATURE`, `AI_DEFAULT_MAX_TOKENS`,
`OPENAI_CHAT_MODEL` (+ existing `OPENAI_API_KEY`/`OPENAI_BASE_URL`), `OLLAMA_BASE_URL`,
`OLLAMA_MODEL`. See `.env.example`.

Note: this is the **chat/LLM** layer. Embeddings have their own provider
abstraction (`app/services/embeddings.py`); the two are intentionally separate.

---

# Retrieval-Augmented Generation (RAG)

Grounded question answering over the knowledge base, with conversation memory and
streaming. Verified end-to-end (20/20).

```
Question → (follow-up expansion) → embed → Qdrant search (tenant-scoped)
  → hydrate + rank → context window → grounded prompt (+ memory) → AI generation → answer + sources
```

## Components (`app/services/rag/`, `app/services/conversation_service.py`)
- `retrieval.py` — embed the query, vector-search (tenant + chatbot filter), hydrate citation metadata (title/source_uri/page) from Postgres, apply `min_score`.
- `context_builder.py` — rank by score, de-duplicate, pack into a bounded **context window**, number each as a citable source `[1]`,`[2]`.
- `prompts.py` — **anti-hallucination** system prompt (answer only from context, say "I don't know" otherwise, cite sources), message assembly with conversation memory, and **follow-up** query expansion (terse/pronoun questions are prepended with the prior turn for retrieval).
- `service.py` — orchestrates non-streaming (`answer`) and streaming (`answer_stream`). Manages its own tenant (RLS) sessions so streaming outlives the request and intermediate commits don't clear the GUC. Short-circuits to an honest fallback (no LLM call) when retrieval is empty.
- `conversation_service.py` — conversations + messages (memory), history loading, counter maintenance.

## Endpoints (permission `conversations:read`)
```
POST /companies/{cid}/chatbots/{bid}/conversations                          create
GET  /companies/{cid}/chatbots/{bid}/conversations                          list
GET  /companies/{cid}/chatbots/{bid}/conversations/{id}/messages            history
POST /companies/{cid}/chatbots/{bid}/conversations/{id}/messages            ask -> {answer, sources[]}
POST /companies/{cid}/chatbots/{bid}/conversations/{id}/messages/stream     ask (SSE)
```
The stream emits `data: {"type":"delta","text":...}` events, then
`data: {"type":"done","sources":[...],"message_id":...}` and `data: [DONE]`.

## Features
- **Conversation memory** — turns persisted to `messages`; recent window replayed into the prompt.
- **Context windows** — `RAG_MAX_CONTEXT_CHARS` budget; highest-scored, de-duplicated chunks.
- **Source retrieval** — every answer returns `sources[]` (document, title, page, score, snippet); stored on the assistant message (`retrieved_chunk_ids`, `citations`).
- **Hallucination reduction** — grounding prompt + empty-retrieval short-circuit to "I don't have enough information" (no fabrication, no LLM cost).
- **Follow-up support** — query expansion using the previous user turn.
- **Streaming** — token deltas via the unified AI provider's `stream()`, then a final sources event.

Generation goes through the **unified AI provider layer**, so `AI_PROVIDER=ollama|openai`
selects the model with no RAG code changes. The chatbot's `system_prompt`,
`temperature`, `top_k`, and `max_tokens` drive persona/retrieval/generation.

## Config
`RAG_TOP_K`, `RAG_MIN_SCORE`, `RAG_MAX_CONTEXT_CHARS`, `RAG_HISTORY_TURNS`, `RAG_PERSONA`.
