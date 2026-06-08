"""Fake OpenAI-compatible server for RAG tests.

Returns an answer derived from the prompt's Context block, so tests can prove the
retrieved context actually reached the model. Supports streaming (SSE).
Run: python tests/_fake_openai.py <port>
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _answer_from(messages: list[dict]) -> str:
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    ctx = ""
    if "Context:" in user:
        after = user.split("Context:", 1)[1]
        ctx = after.split("\n\nQuestion:", 1)[0].strip()
    snippet = ctx[:200].replace("\n", " ")
    return f"Based on the provided context: {snippet}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or b"{}")
        content = _answer_from(req.get("messages", []))

        if req.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for word in content.split(" "):
                chunk = {"choices": [{"delta": {"content": word + " "}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
        else:
            body = json.dumps({
                "model": "fake-gpt",
                "choices": [{
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8077
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
