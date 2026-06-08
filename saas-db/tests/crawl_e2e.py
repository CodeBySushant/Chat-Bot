"""Website crawler end-to-end test (runs against a local test site)."""
from __future__ import annotations

import os
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000/api/v1"
SITE = os.environ.get("TEST_SITE_URL", "http://127.0.0.1:8099/")
P = {"pass": 0, "fail": 0}


def check(name, cond, extra=""):
    if cond:
        P["pass"] += 1
        print(f"  PASS  {name}")
    else:
        P["fail"] += 1
        print(f"  FAIL  {name}  {extra}")


def poll_crawl(c, h, base, job_id, timeout=40):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = c.get(f"{base}/{job_id}", headers=h).json()
        if last["status"] in ("completed", "failed", "cancelled"):
            return last
        time.sleep(0.5)
    return last


def wait_docs_ready(c, h, docs_url, timeout=40):
    deadline = time.time() + timeout
    while time.time() < deadline:
        docs = c.get(docs_url, headers=h).json()
        if docs and all(d["status"] in ("ready", "failed") for d in docs):
            return docs
        time.sleep(0.5)
    return c.get(docs_url, headers=h).json()


def main():
    c = httpx.Client(base_url=BASE, timeout=30)
    c.post("/auth/register", json={"email": "crawl@acme.io", "password": "Sup3rSecret!"})
    tok = c.post("/auth/login", json={"email": "crawl@acme.io", "password": "Sup3rSecret!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    cid = c.post("/companies", headers=h, json={"name": "Crawl Co", "slug": "crawlco"}).json()["id"]
    bot = c.post(f"/companies/{cid}/chatbots", headers=h, json={"name": "Bot", "slug": "bot"}).json()["id"]
    crawls = f"/companies/{cid}/chatbots/{bot}/crawls"
    docs_url = f"/companies/{cid}/chatbots/{bot}/documents"

    print("== Crawl mode (BFS + link discovery) ==")
    r = c.post(crawls, headers=h, json={"start_url": SITE, "mode": "crawl", "max_pages": 20, "max_depth": 2})
    check("start crawl 201", r.status_code == 201, r.text)
    job_id = r.json()["id"]
    check("initial status queued", r.json()["status"] in ("queued", "running"))
    final = poll_crawl(c, h, crawls, job_id)
    check("crawl completed", final and final["status"] == "completed", str(final))
    check("processed >= 5 pages", final and final["pages_processed"] >= 5, str(final))
    check("no failures", final and final["pages_failed"] == 0, str(final))

    print("== Documents stored + deduplicated ==")
    docs = wait_docs_ready(c, h, docs_url)
    urls = {d["title"]: d for d in docs}
    # 5 fetched (index, about, products, products2, contact); products2 is a dup
    # -> 4 unique documents stored.
    check("4 unique docs stored (dedup worked)", len(docs) == 4, f"got {len(docs)}: {[d['title'] for d in docs]}")
    check("all docs ready", all(d["status"] == "ready" for d in docs), str([(d['title'], d['status']) for d in docs]))

    print("== robots.txt + same-domain enforced ==")
    all_titles = " ".join(d["title"] for d in docs)
    check("secret page NOT crawled (robots)", "secret" not in all_titles.lower())
    # external host can't be a document (same-domain filter)
    # (titles are page names; external would not appear)
    check("external page NOT crawled", "external" not in all_titles.lower())

    print("== Boilerplate removal (header/nav/footer/script) ==")
    # find the 'about' doc and inspect its chunk text
    about = next((d for d in docs if d["title"].startswith("about")), None)
    check("about doc exists", about is not None)
    if about:
        chunks = c.get(f"{docs_url}/{about['id']}/chunks", headers=h).json()
        body = " ".join(ch["content"] for ch in chunks)
        check("main content kept", "MAIN_CONTENT_ABOUT" in body, body[:120])
        check("nav removed", "NAVIGATION_MENU" not in body)
        check("header removed", "SITE_HEADER_BRAND" not in body)
        check("footer removed", "FOOTER_LEGAL" not in body)
        check("scripts removed", "TRACKING_SCRIPT" not in body and "ANALYTICS_BOILERPLATE" not in body)

    print("== Search over crawled content ==")
    res = c.post(f"{docs_url}/search", headers=h, json={"query": "autonomous warehouse robots computer vision", "top_k": 3}).json()["results"]
    top = res[0] if res else None
    check("search finds about page", top and top["document_id"] == about["id"], str(top))

    print("== Sitemap mode ==")
    r = c.post(crawls, headers=h, json={"start_url": SITE, "mode": "sitemap", "max_pages": 20})
    check("start sitemap crawl 201", r.status_code == 201, r.text)
    sm_job = r.json()["id"]
    sm_final = poll_crawl(c, h, crawls, sm_job)
    check("sitemap crawl completed", sm_final and sm_final["status"] == "completed", str(sm_final))
    # sitemap lists 4 pages; all already ingested -> deduped (0 new docs), still processed
    check("sitemap processed 4 listed pages", sm_final and sm_final["pages_processed"] == 4, str(sm_final))

    print("== List + cancel endpoints ==")
    jobs = c.get(crawls, headers=h).json()
    check("two jobs listed", len(jobs) == 2, str(len(jobs)))
    cancel = c.post(f"{crawls}/{job_id}/cancel", headers=h)
    check("cancel returns 200", cancel.status_code == 200)

    print("== Validation ==")
    bad = c.post(crawls, headers=h, json={"start_url": "not-a-url", "mode": "crawl"})
    check("invalid start_url rejected", bad.status_code in (422,), bad.text[:120])

    print(f"\nRESULT: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)


if __name__ == "__main__":
    main()
