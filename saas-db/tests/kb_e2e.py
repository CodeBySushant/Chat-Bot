"""Knowledge-base end-to-end test.

Exercises the full pipeline for every supported file type, semantic search,
cross-tenant isolation in Qdrant, deletion, and upload validation.
Run against a live server (see tests/run_kb.sh).
"""
from __future__ import annotations

import io
import sys
import time

import docx
import httpx
from fpdf import FPDF

BASE = "http://127.0.0.1:8000/api/v1"
P = {"pass": 0, "fail": 0}


def check(name, cond, extra=""):
    if cond:
        P["pass"] += 1
        print(f"  PASS  {name}")
    else:
        P["fail"] += 1
        print(f"  FAIL  {name}  {extra}")


def make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


def make_docx(text: str) -> bytes:
    d = docx.Document()
    for line in text.split("\n"):
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


DOCS = {
    "physics.pdf": ("application/pdf", make_pdf(
        "Quantum entanglement links particles across vast distances so that "
        "measuring one instantly affects the other, a phenomenon Einstein "
        "called spooky action at a distance.")),
    "biology.docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", make_docx(
        "The mitochondria is the powerhouse of the cell. It produces ATP "
        "through cellular respiration, supplying chemical energy to organelles.")),
    "geography.txt": ("text/plain", (
        "The capital of France is Paris. Paris sits on the river Seine and is "
        "famous worldwide for the Eiffel Tower and the Louvre museum.").encode()),
    "botany.md": ("text/markdown", (
        "# Photosynthesis\n\nGreen plants convert sunlight, water and carbon "
        "dioxide into glucose using chlorophyll inside their chloroplasts.").encode()),
    "people.csv": ("text/csv", (
        "name,role,city\n"
        "Ada Lovelace,mathematician,London\n"
        "Grace Hopper,computer scientist,New York\n"
        "Katherine Johnson,aerospace engineer,Hampton\n").encode()),
}


def poll_ready(c, headers, base_docs_url, doc_id, timeout=25):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        r = c.get(f"{base_docs_url}/{doc_id}", headers=headers)
        last = r.json()
        if last["status"] in ("ready", "failed"):
            return last
        time.sleep(0.4)
    return last


def setup_company(c, headers, slug):
    cid = c.post("/companies", headers=headers, json={"name": slug.title(), "slug": slug}).json()["id"]
    bot = c.post(f"/companies/{cid}/chatbots", headers=headers,
                 json={"name": f"{slug} bot", "slug": f"{slug}-bot"}).json()
    return cid, bot["id"]


def main():
    c = httpx.Client(base_url=BASE, timeout=30)

    # --- identity + tenants ---
    c.post("/auth/register", json={"email": "kb@acme.io", "password": "Sup3rSecret!", "full_name": "KB"})
    tok = c.post("/auth/login", json={"email": "kb@acme.io", "password": "Sup3rSecret!"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    cidA, botA = setup_company(c, h, "acme")
    docsA = f"/companies/{cidA}/chatbots/{botA}/documents"

    print("== Upload + pipeline for every file type ==")
    doc_ids = {}
    for fname, (mime, data) in DOCS.items():
        r = c.post(docsA, headers=h, files={"file": (fname, data, mime)})
        check(f"upload {fname} 201", r.status_code == 201, r.text)
        if r.status_code != 201:
            continue
        did = r.json()["id"]
        doc_ids[fname] = did
        check(f"{fname} initial status pending", r.json()["status"] == "pending")

    print("== Each document reaches 'ready' with chunks ==")
    for fname, did in doc_ids.items():
        final = poll_ready(c, h, docsA, did)
        check(f"{fname} ready", final and final["status"] == "ready", str(final))
        check(f"{fname} has chunks", final and final["chunk_count"] >= 1, str(final))
        # chunk content is retrievable
        ch = c.get(f"{docsA}/{did}/chunks", headers=h)
        check(f"{fname} chunks endpoint", ch.status_code == 200 and len(ch.json()) >= 1)

    print("== Semantic search relevance ==")
    cases = {
        "Eiffel Tower Paris Seine": "geography.txt",
        "mitochondria powerhouse cell ATP": "biology.docx",
        "quantum entanglement particles Einstein": "physics.pdf",
        "chlorophyll glucose sunlight photosynthesis": "botany.md",
        "Grace Hopper computer scientist": "people.csv",
    }
    for query, expected in cases.items():
        r = c.post(f"{docsA}/search", headers=h, json={"query": query, "top_k": 3})
        results = r.json()["results"]
        top_doc = results[0]["document_id"] if results else None
        check(f"search '{query[:24]}...' -> {expected}",
              top_doc == doc_ids.get(expected), f"got {top_doc} results={len(results)}")

    print("== Cross-tenant isolation (Qdrant filter) ==")
    cidB, botB = setup_company(c, h, "beta")
    docsB = f"/companies/{cidB}/chatbots/{botB}/documents"
    rb = c.post(docsB, headers=h, files={"file": ("safari.txt", b"Zebras and giraffes roam the African savanna in large herds.", "text/plain")})
    bdoc = rb.json()["id"]
    poll_ready(c, h, docsB, bdoc)
    # company B finds its own content
    rb_search = c.post(f"{docsB}/search", headers=h, json={"query": "zebra giraffe savanna", "top_k": 3}).json()["results"]
    check("company B finds its own doc", rb_search and rb_search[0]["document_id"] == bdoc, str(rb_search[:1]))
    # company A must NOT see company B's document for the same query
    ra_search = c.post(f"{docsA}/search", headers=h, json={"query": "zebra giraffe savanna", "top_k": 5}).json()["results"]
    leaked = any(r["document_id"] == bdoc for r in ra_search)
    check("company A cannot see company B's doc", not leaked, f"results={ra_search}")

    print("== Delete document removes chunks + vectors ==")
    target = doc_ids["geography.txt"]
    check("delete 204", c.delete(f"{docsA}/{target}", headers=h).status_code == 204)
    check("get after delete 404", c.get(f"{docsA}/{target}", headers=h).status_code == 404)
    after = c.post(f"{docsA}/search", headers=h, json={"query": "Eiffel Tower Paris", "top_k": 5}).json()["results"]
    check("deleted doc not in search", all(r["document_id"] != target for r in after))

    print("== Upload validation ==")
    check("unsupported .exe -> 422",
          c.post(docsA, headers=h, files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")}).status_code == 422)
    check("magic mismatch (.pdf w/ text) -> 422",
          c.post(docsA, headers=h, files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")}).status_code == 422)
    check("empty file -> 422",
          c.post(docsA, headers=h, files={"file": ("empty.txt", b"", "text/plain")}).status_code == 422)

    print(f"\nRESULT: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)


if __name__ == "__main__":
    main()
