# Deployment Guide — Chatbot SaaS (EmberChat)

A complete, step-by-step guide to putting this project online. It covers **three
deployment paths** — pick ONE based on your situation:

| Path | Best for | Cost | Difficulty |
|------|----------|------|------------|
| **A. VPS (DigitalOcean)** | Real production, the way the project is built | ~$12–24/mo | Medium — recommended |
| **B. PaaS (Railway/Render)** | Avoiding server management | ~$5–20/mo | Medium-fiddly |
| **C. Own PC + Tunnel** | Quick demo / showing a client | Free | Easy but not for real use |

> Local development (your three-terminal Windows setup) is in `ToRun.md`.
> This document is about making the app reachable on the public internet.

---

## What you are deploying (read once)

The app is **not a single program** — it's several pieces that must all run:

- **API** (FastAPI backend) — the brain
- **Worker** — background jobs (document ingestion, crawling)
- **Dashboard** (Next.js) — the UI you log into
- **Widget** — the embeddable chat bubble
- **PostgreSQL** — the database (stores everything)
- **Redis** — cache / rate limiting
- **Qdrant** — vector database (stores embeddings for search)

Path A runs all of these together with one command (Docker). Paths B and C are
workarounds with trade-offs, explained in each section.

---

## Common prerequisites (needed for ALL paths)

### 1. A domain name
You need a domain like `yourbrand.com`. Buy one from Namecheap, GoDaddy, or
Cloudflare (~$10/year). You'll create subdomains:
- `api.yourbrand.com` → backend
- `app.yourbrand.com` → dashboard
- `cdn.yourbrand.com` → widget

(Path C can skip this — the tunnel gives you a free temporary URL.)

### 2. An OpenAI API key (strongly recommended for production)
Local models (Ollama) are too slow for real users on a server with no GPU.
- Go to **platform.openai.com** → sign up → **API keys** → create one.
- Add ~$5 credit (Settings → Billing). `gpt-4o-mini` costs fractions of a cent
  per chat, so this lasts a long time.
- Copy the key (starts with `sk-...`). You'll paste it during setup.

---

# PATH A — VPS with Docker (Recommended)

This is the real deal: one Linux server running the full Docker stack. Best
performance, the way the project was designed. ~30–45 minutes start to finish.

## A1. Create the server

1. Go to **digitalocean.com**, sign up.
2. Click **Create → Droplets**.
3. Choose:
   - **Region**: closest to your users (e.g. Bangalore for India).
   - **Image**: Ubuntu 24.04 LTS.
   - **Size**: Basic → Regular → at least **4 GB RAM / 2 vCPU** (~$24/mo).
     (2 GB works for testing but is tight with all the databases.)
   - **Authentication**: Password (simplest) or SSH key (more secure).
4. Click **Create Droplet**. Wait ~1 minute. Note the server's **IP address**.

## A2. Point your domain at the server

In your domain registrar's DNS settings, create three **A records**, all
pointing to the droplet IP:

| Type | Host | Value |
|------|------|-------|
| A | api | YOUR_SERVER_IP |
| A | app | YOUR_SERVER_IP |
| A | cdn | YOUR_SERVER_IP |

DNS can take 5–60 minutes to propagate. Check with:
`nslookup api.yourbrand.com` — it should return your server IP before you do TLS.

## A3. Connect to the server

From your Windows PowerShell:
```powershell
ssh root@YOUR_SERVER_IP
```
Enter the password (or it logs in via your SSH key). You're now on the server.

## A4. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
docker compose version    # confirm it prints a version
```

## A5. Get the code onto the server

If your project is in a Git repo:
```bash
git clone <your-repo-url> chatbot-saas
cd chatbot-saas/deploy
```

If it's NOT in Git, upload it from your PC (run this in a *local* PowerShell,
not the SSH session):
```powershell
scp -r C:\Users\mesus\Downloads\chatbot-saas\chatbot-saas root@YOUR_SERVER_IP:/root/chatbot-saas
```
Then back in the SSH session: `cd chatbot-saas/deploy`

## A6. Create secret files

```bash
mkdir -p compose/secrets

openssl rand -base64 48 > compose/secrets/jwt_secret_key
echo -n 'StrongPgPassword123' > compose/secrets/postgres_password
printf 'postgresql+asyncpg://app_rw:StrongPgPassword123@postgres:5432/chatbot_saas'   > compose/secrets/database_url
printf 'postgresql+asyncpg://app_admin:StrongPgPassword123@postgres:5432/chatbot_saas' > compose/secrets/database_admin_url

# empty placeholders so mounts don't fail (fill stripe later if you add billing)
echo -n '' > compose/secrets/stripe_api_key
echo -n '' > compose/secrets/stripe_webhook_secret
echo -n '' > compose/secrets/qdrant_api_key
```
Use the SAME password in all three places. Pick your own strong one.

## A7. Configure settings

```bash
cp compose/.env.example compose/.env
nano compose/.env
```
Set these (Ctrl+O to save, Ctrl+X to exit nano):
```env
ENVIRONMENT=production
CORS_ORIGINS=https://app.yourbrand.com
AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
OPENAI_CHAT_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
```

## A8. Replace example.com with your domain

```bash
cd ..    # back to deploy/
grep -rl "example.com" nginx/ tls/ compose/ | xargs sed -i 's/example\.com/yourbrand.com/g'
cd compose
```
This swaps every `example.com` for `yourbrand.com` in the Nginx, TLS, and
compose config in one shot. (Replace `yourbrand.com` with your real domain.)

## A9. Bring up the stack

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
docker compose -f docker-compose.yml ps    # watch until healthy
```
First run builds images — give it a few minutes.

## A10. Run database migrations

```bash
docker compose -f docker-compose.yml run --rm api alembic upgrade head
```

**If it errors** (same gotchas you hit locally, they recur on fresh Postgres):

Permission denied for schema public:
```bash
docker compose -f docker-compose.yml exec postgres psql -U postgres -d chatbot_saas -c "GRANT CREATE, USAGE ON SCHEMA public TO app_admin, app_rw;"
```
Permission denied to create extension pgcrypto:
```bash
docker compose -f docker-compose.yml exec postgres psql -U postgres -d chatbot_saas -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"
```
Then re-run the migration. It should end at `0006_seed_platform`.

## A11. Get HTTPS certificates

```bash
cd ..    # deploy/
chmod +x tls/init-letsencrypt.sh
./tls/init-letsencrypt.sh
```
This requests free Let's Encrypt certs for your three subdomains. DNS (step A2)
MUST be resolving first or this fails.

## A12. Make yourself super-admin

Register your account at `https://app.yourbrand.com` first, then:
```bash
cd compose
docker compose -f docker-compose.yml exec postgres psql -U postgres -d chatbot_saas -c "UPDATE users SET is_superuser = true WHERE email = 'you@yourbrand.com';"
```
Log out and back in.

## A13. Done — verify

- Dashboard: `https://app.yourbrand.com`
- API health: `https://api.yourbrand.com/healthz`
- API docs: `https://api.yourbrand.com/docs`

Register → company → chatbot → upload a document → chat. Live for real users.

---

# PATH B — PaaS (Railway / Render)

No server to manage; the platform runs each piece for you. The catch: this app
has 4 app services + 3 databases, so you wire up multiple components. More
clicking than Path A, and less faithful to the original design.

## B1. The shape of it

On Railway (railway.app) you create **one project** and add these as separate
services:
- **PostgreSQL** (Railway has a 1-click Postgres)
- **Redis** (1-click)
- **Qdrant** (deploy from the `qdrant/qdrant` Docker image)
- **API** — deploy from your repo, root `saas-db/`, using `Dockerfile.backend`
- **Worker** — same repo/`saas-db`, using `Dockerfile.worker`
- **Dashboard** — from `dashboard/`, using `Dockerfile.frontend`
- **Widget** — from `widget/` (optional; can host the built file on any static host)

## B2. Steps

1. Sign up at **railway.app**, create a **New Project**.
2. **Add PostgreSQL** and **Redis** from Railway's database catalog (1-click each).
3. **Add Qdrant**: New → Deploy from Docker Image → `qdrant/qdrant:v1.12.1`.
4. **Add the API**: New → Deploy from GitHub repo → set the root/Dockerfile to
   `deploy/docker/Dockerfile.backend` with build context `saas-db/`.
   Then set environment variables (Variables tab):
   - `DATABASE_URL` = Railway's Postgres URL but with `+asyncpg`, user `app_rw`
   - `DATABASE_ADMIN_URL` = same with user `app_admin`
   - `JWT_SECRET_KEY` = a random string
   - `REDIS_URL` = Railway's Redis URL
   - `QDRANT_URL` = the internal Qdrant service URL
   - `AI_PROVIDER=openai`, `OPENAI_API_KEY=sk-...`
   - `CORS_ORIGINS` = your dashboard's public URL
5. **Add the Worker**: same repo, `Dockerfile.worker`, same env vars.
6. **Add the Dashboard**: from `dashboard/`, set
   `NEXT_PUBLIC_API_BASE` = the API service's public URL.
7. **Run migrations**: in the API service's shell (Railway gives you one), run
   `alembic upgrade head`. Apply the same schema-grant / pgcrypto fixes from
   A10 if needed (run psql against the Railway Postgres).
8. **Custom domains**: in each service's Settings → Networking, add your
   subdomains (`api.`, `app.`) and point DNS CNAMEs at Railway as instructed.

## B3. Honest caveats for Path B
- The roles `app_rw`/`app_admin` aren't auto-created (no init script runs), so
  you must create them manually on the Railway Postgres with the SQL from
  `deploy/postgres/init/00-roles.sql` before migrating.
- You manage 7 services and their interconnections by hand — fiddly.
- **Render** works the same way (Web Services + managed Postgres/Redis + a
  private Qdrant service). Same trade-offs.

Use Path B only if you specifically don't want to run a server. Otherwise Path A
is simpler for this particular app.

---

# PATH C — Own PC + Tunnel (Demo only)

For quickly showing the running app to someone over the internet, without a
server. **Not for real production** — your PC must stay on, it's slower, and
it's a security exposure. Good for a 10-minute client demo.

## C1. Keep the app running locally
Have all three local terminals up (worker, API, dashboard) per `ToRun.md`, plus
Postgres running. Confirm `http://localhost:3000` works on your machine.

## C2. Install a tunnel
Two easy options:

**Cloudflare Tunnel (free, no signup needed for quick mode):**
```powershell
# install cloudflared (one time): winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:3000
```
It prints a public `https://...trycloudflare.com` URL. Share that.

**ngrok (free tier):**
1. Sign up at ngrok.com, install, run `ngrok config add-authtoken <token>`.
2. `ngrok http 3000` → gives a public URL.

## C3. Important limitation
The dashboard talks to the API at `localhost:8000`. Over a tunnel, the browser
is on someone else's machine, so `localhost` won't reach your API. For a real
shared demo you'd also tunnel the API (port 8000) and set the dashboard's
`NEXT_PUBLIC_API_BASE_URL` to that API tunnel URL, then restart the dashboard.
This is why Path C is demo-grade only — it's quick but brittle.

---

# After deployment (all paths)

## Post-deploy checklist
- [ ] DNS resolves (Paths A/B)
- [ ] All services healthy / running
- [ ] Migrations ran to `0006_seed_platform`
- [ ] HTTPS works (Paths A/B)
- [ ] Super-admin account flagged
- [ ] Full test: signup → company → chatbot → upload → ready → chat answers

## Give yourself the unlimited plan (optional)
The free plan caps you at 1 chatbot. To lift all limits for your own company,
add an enterprise subscription (replace the company id):
```bash
# inside the postgres container (Path A) or against your managed DB (Path B)
psql -U postgres -d chatbot_saas -c "INSERT INTO subscriptions (id, company_id, plan_code, status, created_at) VALUES (gen_random_uuid(), 'YOUR_COMPANY_ID', 'enterprise', 'active', now());"
```

## Day-2 operations (Path A)
```bash
# logs
docker compose -f docker-compose.yml logs -f api
docker compose -f docker-compose.yml logs -f worker

# restart a service
docker compose -f docker-compose.yml restart api

# deploy new code
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml run --rm api alembic upgrade head
```

## Backups (Path A)
Scripts live in `deploy/backups/` (`pg_backup.sh`, `qdrant_backup.sh`,
`s3_sync.sh`). Schedule with cron; test restores with `pg_restore.sh`.

## Monitoring (Path A, optional)
```bash
docker compose -f compose/docker-compose.monitoring.yml up -d
```
Prometheus + Grafana + Loki + OpenTelemetry. Dashboards in `monitoring/grafana/`.

---

# Troubleshooting

**API won't start / "connection refused" to Postgres**
Database isn't ready or roles weren't created. Check `docker compose ps`; ensure
postgres is healthy; verify `00-roles.sql` ran (Path A runs it automatically;
Paths B/C you create roles manually).

**"permission denied for schema public" during migration**
`GRANT CREATE, USAGE ON SCHEMA public TO app_admin, app_rw;` (see A10).

**"permission denied to create extension pgcrypto"**
`CREATE EXTENSION IF NOT EXISTS pgcrypto;` as the postgres superuser (see A10).

**TLS cert request fails**
DNS isn't resolving yet, or a subdomain is missing. Confirm all three A records
point to the server and `nslookup` returns the right IP, then re-run the script.

**Chatbot says "(no response)"**
The LLM isn't reachable. Confirm `AI_PROVIDER=openai` and a valid
`OPENAI_API_KEY` are set, then restart the API.

**Dashboard loads but every API call fails**
`NEXT_PUBLIC_API_BASE` (frontend) must point at the public API URL, and the
API's `CORS_ORIGINS` must include the dashboard's URL. Fix both, redeploy.

---

# Recommendation

For a real product: **Path A (VPS + Docker)**. It's what the project is built
for, runs everything together, and is the least fragile. Use a 4 GB DigitalOcean
droplet, your own domain, and an OpenAI key. Paths B and C exist for specific
situations (no-server preference, or a quick demo) but trade simplicity or
robustness to get there.