"""Public widget API e2e: key auth, config, conversation, streaming, leads,
domain allowlist, and tenant-isolation guard. No user JWT on widget calls.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
P = {"pass": 0, "fail": 0}


def check(name, cond, extra=""):
    P["pass" if cond else "fail"] += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {name}  {'' if cond else extra}")


def psql(sql: str):
    subprocess.run(
        ["su", "postgres", "-c",
         f"/usr/lib/postgresql/16/bin/psql -h /tmp -p 5432 -d chatbot_saas -q -c \"{sql}\""],
        check=False, capture_output=True,
    )


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
    # --- authenticated setup: company, chatbot, ingest a doc ---
    c.post("/auth/register", json={"email": "widget@acme.io", "password": "Sup3rSecret!"})
    tok = c.post("/auth/login", json={"email": "widget@acme.io", "password": "Sup3rSecret!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    cid = c.post("/companies", headers=h, json={"name": "Widget Co", "slug": "widgetco"}).json()["id"]
    bot = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Helpbot", "slug": "helpbot"}).json()
    bot_id, public_key = bot["id"], bot["public_key"]
    docs_url = f"/companies/{cid}/chatbots/{bot_id}/documents"
    doc = (b"Our refund policy: customers can request a full refund within 30 days of purchase. "
           b"Contact support@acme.io to start a refund.")
    c.post(docs_url, headers=h, files={"file": ("policy.txt", doc, "text/plain")})
    wait_ready(c, h, docs_url)

    # --- publish the chatbot (no publish endpoint yet; flip status directly) ---
    psql(f"UPDATE chatbots SET status='active' WHERE id='{bot_id}';")

    pub = httpx.Client(base_url=BASE, timeout=30)  # NO auth header — public client

    print("== Config (public, no JWT) ==")
    r = pub.get(f"/widget/{public_key}/config")
    check("config 200 without auth", r.status_code == 200, r.text[:120])
    cfg = r.json()
    check("config has chatbot name", cfg.get("chatbot_name") == "Helpbot")
    check("config has greeting + color", bool(cfg.get("greeting")) and cfg.get("primary_color", "").startswith("#"))

    print("== Invalid key rejected ==")
    check("unknown key -> 404", pub.get("/widget/pk_does_not_exist/config").status_code == 404)

    print("== Start conversation (public) ==")
    r = pub.post(f"/widget/{public_key}/conversations", json={"visitor_id": "v-123"})
    check("conversation 200", r.status_code == 200, r.text[:120])
    conv_id = r.json()["conversation_id"]

    print("== Streaming answer (grounded) ==")
    deltas, done = [], None
    with pub.stream("POST", f"/widget/{public_key}/conversations/{conv_id}/messages/stream",
                    json={"question": "What is your refund policy?"}) as resp:
        check("stream 200", resp.status_code == 200)
        for line in resp.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            ev = json.loads(payload)
            if ev.get("type") == "delta":
                deltas.append(ev["text"])
            elif ev.get("type") == "done":
                done = ev
    answer = "".join(deltas)
    check("stream produced tokens", len(deltas) >= 2, f"{len(deltas)}")
    check("answer grounded (refund)", "refund" in answer.lower(), answer[:120])
    check("done event has sources", done and len(done.get("sources", [])) >= 1, str(done))

    print("== Foreign conversation id rejected (no IDOR) ==")
    fake = "00000000-0000-0000-0000-000000000000"
    rr = pub.post(f"/widget/{public_key}/conversations/{fake}/messages/stream", json={"question": "hi"})
    check("foreign conversation -> 404", rr.status_code == 404, str(rr.status_code))

    print("== Lead capture (public) ==")
    r = pub.post(f"/widget/{public_key}/leads",
                 json={"name": "Jane", "email": "jane@buyer.com", "conversation_id": conv_id})
    check("lead 200", r.status_code == 200, r.text[:120])
    # verify it landed with source=widget
    out = subprocess.run(
        ["su", "postgres", "-c",
         f"/usr/lib/postgresql/16/bin/psql -h /tmp -p 5432 -d chatbot_saas -tA -c "
         f"\"SELECT source FROM leads WHERE email='jane@buyer.com';\""],
        capture_output=True, text=True,
    ).stdout.strip()
    check("lead persisted with source=widget", out == "widget", out)
    check("lead requires a contact field", pub.post(f"/widget/{public_key}/leads", json={}).status_code in (400, 403))

    print("== Domain allowlist enforcement ==")
    psql(f"INSERT INTO widget_configurations (chatbot_id, company_id, allowed_domains) "
         f"VALUES ('{bot_id}', '{cid}', ARRAY['example.com']) "
         f"ON CONFLICT (chatbot_id) DO UPDATE SET allowed_domains=ARRAY['example.com'];")
    blocked = pub.get(f"/widget/{public_key}/config", headers={"Origin": "https://evil.com"})
    allowed = pub.get(f"/widget/{public_key}/config", headers={"Origin": "https://app.example.com"})
    check("disallowed origin -> 403", blocked.status_code == 403, str(blocked.status_code))
    check("allowed origin (subdomain) -> 200", allowed.status_code == 200, str(allowed.status_code))

    print(f"\nRESULT: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)


if __name__ == "__main__":
    main()
