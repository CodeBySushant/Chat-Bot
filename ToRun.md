# How to Run the Chatbot SaaS

Daily startup guide. The heavy setup (PostgreSQL, virtual environment, database
migrations) is already done and permanent — you only run the three commands
below. PostgreSQL starts automatically with Windows.

---

## Start everything (3 terminals)

Open **three separate PowerShell windows** and run one block in each.

### Terminal 1 — Worker
```powershell
cd C:\Users\mesus\Downloads\chatbot-saas\chatbot-saas\saas-db
.\.venv\Scripts\python.exe -m app.worker_main
```
Wait until it prints `Worker started` and goes quiet. Leave it open.

### Terminal 2 — API (backend)
```powershell
cd C:\Users\mesus\Downloads\chatbot-saas\chatbot-saas\saas-db
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
Wait for `Application startup complete`. Check it at http://127.0.0.1:8000/docs

### Terminal 3 — Dashboard (frontend)
```powershell
cd C:\Users\mesus\Downloads\chatbot-saas\chatbot-saas\dashboard
npm run dev
```
Then open the app at **http://localhost:3000**

---

## Stop everything

Press **Ctrl+C** in each terminal, or just close the windows.

---

## Give the chatbot company data

1. Log in at http://localhost:3000
2. Create a company, then create a chatbot.
3. Go to **Knowledge Base → Documents** and upload files
   (PDF, DOCX, TXT, MD, CSV — up to 25 MB each), **or**
   use the **Crawl** page to point it at a website.
4. Watch a document go `pending → processing → ready`
   (that's Terminal 1, the worker, indexing it).

---

## Get generated chat answers (LLM)

Retrieval/search works out of the box. For the bot to *write* answers it needs
an LLM. The default is Ollama.

- **Ollama:** have it running with the model pulled — `ollama pull llama3.1`
- **OpenAI:** edit `saas-db\.env` → set `AI_PROVIDER=openai` and
  `OPENAI_API_KEY=sk-...`, then restart Terminal 2.

---

## Things you do NOT repeat

These were one-time. Skip them on normal startup:
- `pip install -r requirements.txt`
- `npm install`
- `createdb` / roles SQL
- `alembic upgrade head`

**Exceptions (rare):**
- Edited `requirements.txt` → re-run the pip install.
- Pulled new code with DB changes → re-run `alembic upgrade head`.

---

## Troubleshooting

**Worker or API shows a connection error on startup**
PostgreSQL service probably didn't start. Check and start it:
```powershell
Get-Service -Name postgresql*
Start-Service postgresql-x64-17
```

**`createdb` / `psql` not recognized**
Use the full path:
```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d chatbot_saas
```

**Need to confirm Postgres is listening**
```powershell
Test-NetConnection -ComputerName localhost -Port 5432
```
`TcpTestSucceeded : True` means it's up.