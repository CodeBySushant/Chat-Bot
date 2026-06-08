"""RAG end-to-end test (app + fake OpenAI server + live Postgres/Qdrant)."""
from __future__ import annotations

import json
import sys
import time

import httpx

from app.services.ai import ChatMessage
from app.services.rag import prompts

BASE = "http://127.0.0.1:8000/api/v1"
P = {"pass": 0, "fail": 0}


def check(name, cond, extra=""):
    if cond:
        P["pass"] += 1
        print(f"  PASS  {name}")
    else:
        P["fail"] += 1
        print(f"  FAIL  {name}  {extra}")


def wait_ready(c, h, docs_url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = c.get(docs_url, headers=h).json()
        if docs and all(d["status"] in ("ready", "failed") for d in docs):
            return docs
        time.sleep(0.4)
    return c.get(docs_url, headers=h).json()


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/auth/register", json={"email": "rag@acme.io", "password": "Sup3rSecret!"})
    tok = c.post("/auth/login", json={"email": "rag@acme.io", "password": "Sup3rSecret!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    cid = c.post("/companies", headers=h, json={"name": "RAG Co", "slug": "ragco"}).json()["id"]
    bot = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Bot", "slug": "bot"}).json()["id"]
    docs_url = f"/companies/{cid}/chatbots/{bot}/documents"
    convs = f"/companies/{cid}/chatbots/{bot}/conversations"

    print("== Unit: follow-up query expansion ==")
    hist = [ChatMessage("user", "What is the capital of France?"),
            ChatMessage("assistant", "Paris.")]
    expanded = prompts.build_retrieval_query("What river is it on?", hist)
    check("follow-up prepends prior question", "capital of France" in expanded, expanded)
    standalone = prompts.build_retrieval_query(
        "Explain the entire history of French government in detail please", [])
    check("standalone question not expanded", standalone.startswith("Explain the entire"), standalone)

    print("== Setup: ingest a document ==")
    doc_text = (b"The capital of France is Paris. Paris sits on the river Seine. "
                b"The Eiffel Tower is the most famous landmark in Paris, France.")
    r = c.post(docs_url, headers=h, files={"file": ("france.txt", doc_text, "text/plain")})
    france_id = r.json()["id"]
    docs = wait_ready(c, h, docs_url)
    check("doc ingested ready", docs and docs[0]["status"] == "ready", str(docs))

    print("== Create conversation ==")
    conv = c.post(convs, headers=h, json={"channel": "api", "title": "t"})
    check("create conversation 201", conv.status_code == 201, conv.text)
    conv_id = conv.json()["id"]

    print("== Ask (retrieval -> context -> generation -> sources) ==")
    a1 = c.post(f"{convs}/{conv_id}/messages", headers=h, json={"question": "What is the capital of France?"})
    check("ask 200", a1.status_code == 200, a1.text)
    ans = a1.json()
    check("answer grounded in context (mentions Paris)", "Paris" in ans["answer"], ans["answer"][:150])
    check("sources returned", len(ans["sources"]) >= 1, str(ans["sources"]))
    check("source is the france doc", ans["sources"][0]["document_id"] == france_id)
    check("source has snippet+title", bool(ans["sources"][0]["snippet"]) and ans["sources"][0]["title"] is not None)

    print("== Conversation memory ==")
    msgs = c.get(f"{convs}/{conv_id}/messages", headers=h).json()
    check("history has user+assistant", len(msgs) == 2 and msgs[0]["role"] == "user" and msgs[1]["role"] == "assistant", str([m["role"] for m in msgs]))
    check("assistant message stored citations", len(msgs[1]["citations"]) >= 1)

    print("== Follow-up support ==")
    a2 = c.post(f"{convs}/{conv_id}/messages", headers=h, json={"question": "What river is it on?"})
    ans2 = a2.json()
    check("follow-up retrieves same doc", ans2["sources"] and ans2["sources"][0]["document_id"] == france_id, str(ans2["sources"][:1]))
    check("follow-up answer grounded (Seine)", "Seine" in ans2["answer"], ans2["answer"][:150])
    msgs = c.get(f"{convs}/{conv_id}/messages", headers=h).json()
    check("history grew to 4", len(msgs) == 4, str(len(msgs)))

    print("== Streaming response (SSE) ==")
    deltas, done_event = [], None
    with httpx.Client(base_url=BASE, timeout=30) as sc:
        with sc.stream("POST", f"{convs}/{conv_id}/messages/stream", headers=h,
                       json={"question": "Tell me about the Eiffel Tower"}) as resp:
            check("stream 200", resp.status_code == 200)
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if payload == "[DONE]":
                    break
                evt = json.loads(payload)
                if evt.get("type") == "delta":
                    deltas.append(evt["text"])
                elif evt.get("type") == "done":
                    done_event = evt
    streamed = "".join(deltas)
    check("stream produced tokens", len(deltas) >= 2, f"{len(deltas)} deltas")
    check("streamed answer grounded", "Eiffel" in streamed or "Paris" in streamed, streamed[:150])
    check("stream done event has sources", done_event and len(done_event["sources"]) >= 1, str(done_event))

    print("== Hallucination reduction: empty knowledge base ==")
    c.post(f"/companies/{cid}/billing/subscribe", headers=h, json={"plan_code": "pro"})
    bot2 = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Empty", "slug": "empty"}).json()["id"]
    convs2 = f"/companies/{cid}/chatbots/{bot2}/conversations"
    conv2 = c.post(convs2, headers=h, json={"channel": "api"}).json()["id"]
    a3 = c.post(f"{convs2}/{conv2}/messages", headers=h, json={"question": "What is your refund policy?"}).json()
    check("no-context -> no sources", a3["sources"] == [], str(a3["sources"]))
    check("no-context -> honest fallback", "don't have enough information" in a3["answer"], a3["answer"][:150])

    print(f"\nRESULT: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)


if __name__ == "__main__":
    main()
