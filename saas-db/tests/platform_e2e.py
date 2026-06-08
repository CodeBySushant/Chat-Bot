"""Platform e2e: lead lifecycle, quota enforcement, subscription lifecycle,
analytics accuracy, admin permission gating, and the durable job queue (DLQ).

HTTP flows run against the live server; analytics rollup + job queue are driven
in-process in a single asyncio.run() (engines are loop-bound) at the end.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import uuid
from datetime import date

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
P = {"pass": 0, "fail": 0}


def check(name, cond, extra=""):
    P["pass" if cond else "fail"] += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {'' if cond else '<-- ' + str(extra)[:160]}")


def psql(sql: str, read=False):
    flag = "-tA" if read else "-q"
    out = subprocess.run(
        ["su", "postgres", "-c",
         f"/usr/lib/postgresql/16/bin/psql -h /tmp -p 5432 -d chatbot_saas {flag} -c \"{sql}\""],
        capture_output=True, text=True,
    )
    return out.stdout.strip()


def wait_ready(c, h, url, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        docs = c.get(url, headers=h).json()
        if docs and all(d["status"] in ("ready", "failed") for d in docs):
            return docs
        time.sleep(0.4)
    return c.get(url, headers=h).json()


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    EMAIL = "platform@acme.io"
    c.post("/auth/register", json={"email": EMAIL, "password": "Sup3rSecret!"})
    tok = c.post("/auth/login", json={"email": EMAIL, "password": "Sup3rSecret!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    me = c.get("/users/me", headers=h).json()
    user_id = me["user"]["id"]
    cid = c.post("/companies", headers=h, json={"name": "Platform Co", "slug": "platformco"}).json()["id"]

    print("== Setup: first chatbot on free plan ==")
    bot1 = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Bot1", "slug": "bot1"})
    check("free plan allows first chatbot", bot1.status_code == 201, bot1.text)
    bot1 = bot1.json()
    bot_id, public_key = bot1["id"], bot1["public_key"]
    docs_url = f"/companies/{cid}/chatbots/{bot_id}/documents"
    c.post(docs_url, headers=h, files={"file": ("p.txt", b"Refunds are available within 30 days. Email support@acme.io.", "text/plain")})
    wait_ready(c, h, docs_url)
    psql(f"UPDATE chatbots SET status='active' WHERE id='{bot_id}';")

    print("== Quota enforcement (free chatbots limit = 1) ==")
    bot2 = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Bot2", "slug": "bot2"})
    check("2nd chatbot blocked on free -> 402", bot2.status_code == 402, bot2.status_code)
    check("402 body names the metric", "chatbots" in bot2.text.lower(), bot2.text[:160])

    print("== Subscription lifecycle ==")
    plans = c.get(f"/companies/{cid}/billing/plans", headers=h)
    check("plans list returns 5", plans.status_code == 200 and len(plans.json()) == 5, plans.text[:120])
    sub0 = c.get(f"/companies/{cid}/billing/subscription", headers=h).json()
    check("default plan is free", sub0["plan_code"] == "free", sub0)
    up = c.post(f"/companies/{cid}/billing/subscribe", headers=h, json={"plan_code": "pro"})
    check("upgrade to pro 200", up.status_code == 200, up.text[:160])
    check("pro entitlements applied (chatbots=10)", up.json()["entitlements"].get("chatbots") == 10, up.json().get("entitlements"))

    print("== Quota lifts after upgrade ==")
    bot2b = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Bot2", "slug": "bot2"})
    check("2nd chatbot now allowed on pro", bot2b.status_code == 201, bot2b.text[:160])

    print("== Downgrade + cancel ==")
    down = c.post(f"/companies/{cid}/billing/subscribe", headers=h, json={"plan_code": "starter"})
    check("downgrade to starter", down.status_code == 200 and down.json()["entitlements"]["chatbots"] == 3, down.text[:120])
    canc = c.post(f"/companies/{cid}/billing/cancel", headers=h)
    check("cancel returns 200", canc.status_code == 200, canc.text[:120])
    check("cancellation recorded", psql(f"SELECT canceled_at IS NOT NULL FROM subscriptions WHERE company_id='{cid}';", read=True).startswith("t"))

    print("== Lead lifecycle ==")
    l1 = c.post(f"/companies/{cid}/leads", headers=h, json={"chatbot_id": bot_id, "name": "Alice Buyer", "email": "alice@corp.com", "company": "Corp", "source": "manual"})
    check("manual lead create 201", l1.status_code == 201, l1.text[:160])
    lead_id = l1.json()["id"]
    c.post(f"/companies/{cid}/leads", headers=h, json={"chatbot_id": bot_id, "name": "Bob Prospect", "email": "bob@xyz.com"})
    lst = c.get(f"/companies/{cid}/leads", headers=h).json()
    check("list leads total>=2", lst["total"] >= 2, lst.get("total"))
    srch = c.get(f"/companies/{cid}/leads?q=alice", headers=h).json()
    check("search by name finds Alice", srch["total"] == 1 and srch["items"][0]["name"] == "Alice Buyer", srch)
    filt = c.get(f"/companies/{cid}/leads?status=new", headers=h).json()
    check("filter status=new", filt["total"] >= 2, filt.get("total"))
    upd = c.patch(f"/companies/{cid}/leads/{lead_id}", headers=h, json={"status": "qualified"})
    check("update status->qualified", upd.status_code == 200 and upd.json()["status"] == "qualified", upd.text[:120])
    asg = c.post(f"/companies/{cid}/leads/{lead_id}/assign", headers=h, json={"assignee_id": user_id})
    check("assign lead", asg.status_code == 200 and asg.json()["assigned_to"] == user_id, asg.text[:120])
    note = c.post(f"/companies/{cid}/leads/{lead_id}/notes", headers=h, json={"body": "Called, interested in Pro."})
    check("add note 201", note.status_code == 201, note.text[:120])
    tl = c.get(f"/companies/{cid}/leads/{lead_id}/timeline", headers=h).json()
    types = {a["activity_type"] for a in tl}
    check("timeline has created/status_changed/assigned/note_added",
          {"created", "status_changed", "assigned", "note_added"} <= types, types)
    exp = c.get(f"/companies/{cid}/leads/export", headers=h)
    check("export CSV", exp.status_code == 200 and exp.text.startswith("id,name,email"), exp.text[:60])
    check("CSV includes a lead", "alice@corp.com" in exp.text)
    la = c.get(f"/companies/{cid}/leads/analytics", headers=h).json()
    check("lead analytics shape", "by_status" in la and "conversion_rate" in la, la)

    print("== Widget lead capture logs an activity ==")
    pub = httpx.Client(base_url=BASE, timeout=30)
    conv = pub.post(f"/widget/{public_key}/conversations", json={"visitor_id": "v1"}).json()["conversation_id"]
    # stream one message to generate conversation + messages (analytics + usage)
    deltas = 0
    with pub.stream("POST", f"/widget/{public_key}/conversations/{conv}/messages/stream",
                    json={"question": "What is your refund policy?"}) as r:
        for line in r.iter_lines():
            if line.startswith("data:") and '"delta"' in line:
                deltas += 1
    check("widget message streamed", deltas >= 1, deltas)
    wl = pub.post(f"/widget/{public_key}/leads", json={"name": "Wendy Widget", "email": "wendy@web.com", "conversation_id": conv})
    check("widget lead captured", wl.status_code == 200, wl.text[:120])
    widget_lead = psql("SELECT id FROM leads WHERE email='wendy@web.com';", read=True)
    act = psql(f"SELECT count(*) FROM lead_activities WHERE lead_id='{widget_lead}' AND activity_type='created';", read=True)
    check("widget lead has 'created' activity", act == "1", act)

    print("== Admin permission gating ==")
    denied = c.get("/admin/metrics", headers=h)
    check("non-superuser -> 403", denied.status_code == 403, denied.status_code)
    psql(f"UPDATE users SET is_superuser=true WHERE email='{EMAIL}';")
    m = c.get("/admin/metrics", headers=h)
    check("superuser metrics 200", m.status_code == 200 and "total_conversations" in m.json(), m.text[:160])
    rev = c.get("/admin/dashboards/revenue", headers=h)
    check("revenue dashboard (mrr/arr/churn)", rev.status_code == 200 and {"mrr", "arr", "churn_rate"} <= set(rev.json()), rev.text[:160])
    ops = c.get("/admin/dashboards/operations", headers=h)
    check("operations dashboard (job_queue/dead_letter)", ops.status_code == 200 and "job_queue" in ops.json() and "dead_letter" in ops.json(), ops.text[:160])
    sec = c.get("/admin/dashboards/security", headers=h)
    check("security dashboard (failed_logins)", sec.status_code == 200 and "failed_logins_7d" in sec.json(), sec.text[:160])
    tn = c.get("/admin/tenants", headers=h)
    check("tenant list", tn.status_code == 200 and tn.json()["total"] >= 1, tn.text[:120])

    print("== Tenant analytics dashboard ==")
    dash = c.get(f"/companies/{cid}/analytics/dashboard", headers=h).json()
    check("dashboard daily_conversations present", len(dash["daily_conversations"]) >= 1, dash.get("daily_conversations"))
    check("conversion funnel has qualified", dash["conversion_funnel"].get("qualified", 0) >= 1, dash.get("conversion_funnel"))
    check("top_chatbots present", len(dash["top_chatbots"]) >= 1, dash.get("top_chatbots"))
    check("popular_questions present", len(dash["popular_questions"]) >= 1, dash.get("popular_questions"))

    # ---------- in-process: analytics rollup accuracy + job queue/DLQ ----------
    print("== Analytics rollup accuracy + job queue (in-process) ==")

    async def in_process():
        from app.db.session import tenant_session, dispose_engines
        from app.services import analytics_service
        from app.services.jobs import queue
        from app.workers import job_worker

        company = uuid.UUID(cid)
        today = date.today()
        # direct rollup
        async with tenant_session(company) as db:
            res = await analytics_service.rollup_day(db, company_id=company, day=today)
        check("rollup conversations>=1", res["conversations"] >= 1, res)
        check("rollup messages>=2 (user+assistant)", res["messages"] >= 2, res)
        check("rollup leads>=3", res["leads"] >= 3, res)

        # job queue: dead-letter after exhausting attempts
        jid = await queue.enqueue("_test_fail", {"x": 1}, max_attempts=1)
        outcome = await job_worker.run_once("tw")
        check("failing job -> dead-letter", outcome == "dead", outcome)
        st = psql(f"SELECT status FROM jobs WHERE id='{jid}';", read=True)
        check("DLQ status persisted", st == "dead", st)

        # job queue: successful rollup task
        jid2 = await queue.enqueue("analytics_rollup", {"company_id": cid, "day": today.isoformat()})
        out2 = await job_worker.run_once("tw")
        check("rollup job succeeds", out2 == "succeeded", out2)
        st2 = psql(f"SELECT status FROM jobs WHERE id='{jid2}';", read=True)
        check("succeeded status persisted", st2 == "succeeded", st2)

        # idempotency: only one company-level analytics_daily row for today
        rows = psql(f"SELECT count(*) FROM analytics_daily WHERE company_id='{cid}' AND day='{today.isoformat()}' AND chatbot_id IS NULL;", read=True)
        check("rollup idempotent (single daily row)", rows == "1", rows)

        await dispose_engines()

    asyncio.run(in_process())

    print(f"\nRESULT: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)


if __name__ == "__main__":
    main()
