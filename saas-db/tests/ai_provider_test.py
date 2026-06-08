"""Unified AI provider layer test.

Spins up a local fake server that speaks both the OpenAI (/v1/chat/completions,
SSE) and Ollama (/api/chat, NDJSON) wire protocols, including streaming and error
statuses, then exercises both providers, the factory's env-driven switch, error
mapping, and future-provider registration. No real APIs required.
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import app.core.config as cfg
from app.services import ai
from app.services.ai import (
    AIAuthError,
    AIConfigError,
    AIRateLimitError,
    AIResponseError,
    ChatMessage,
    ChatProvider,
    CompletionResult,
)
from app.services.ai.ollama_provider import OllamaProvider
from app.services.ai.openai_provider import OpenAIProvider

P = {"pass": 0, "fail": 0}
PIECES = ["Hello", " streamed", " world"]


def check(name, cond, extra=""):
    if cond:
        P["pass"] += 1
        print(f"  PASS  {name}")
    else:
        P["fail"] += 1
        print(f"  FAIL  {name}  {extra}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _json(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length) or b"{}")
        model = req.get("model", "")
        stream = req.get("stream", False)

        if model == "err-401":
            return self._json(401, {"error": "unauthorized"})
        if model == "err-429":
            return self._json(429, {"error": "rate limited"})
        if model == "err-bad":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"NOT VALID JSON")
            return

        if self.path.endswith("/chat/completions"):
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for p in PIECES:
                    line = "data: " + json.dumps(
                        {"choices": [{"delta": {"content": p}}]}
                    ) + "\n\n"
                    self.wfile.write(line.encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self._json(200, {
                    "model": model,
                    "choices": [{
                        "message": {"role": "assistant", "content": "Hello from OpenAI"},
                        "finish_reason": "stop",
                    }],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
                })
        elif self.path.endswith("/api/chat"):
            if stream:
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                for p in PIECES:
                    self.wfile.write(
                        (json.dumps({"message": {"content": p}, "done": False}) + "\n").encode()
                    )
                self.wfile.write(
                    (json.dumps({
                        "message": {"content": ""}, "done": True,
                        "done_reason": "stop", "prompt_eval_count": 3, "eval_count": 5,
                    }) + "\n").encode()
                )
            else:
                self._json(200, {
                    "model": model,
                    "message": {"role": "assistant", "content": "Hello from Ollama"},
                    "done": True, "done_reason": "stop",
                    "prompt_eval_count": 3, "eval_count": 5,
                })
        else:
            self._json(404, {"error": "not found"})


def start_server() -> tuple[ThreadingHTTPServer, str]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host, port = srv.server_address
    return srv, f"http://{host}:{port}"


def mk_openai(base) -> OpenAIProvider:
    return OpenAIProvider(api_key="test", base_url=base + "/v1", model="gpt-x",
                          timeout=10, default_temperature=0.2, default_max_tokens=64)


def mk_ollama(base) -> OllamaProvider:
    return OllamaProvider(base_url=base, model="llama3.1",
                          timeout=10, default_temperature=0.2, default_max_tokens=64)


async def run(base: str):
    msgs = [ChatMessage("system", "You are helpful"), ChatMessage("user", "Hi")]

    print("== OpenAI provider ==")
    op = mk_openai(base)
    res = await op.complete(msgs)
    check("openai complete text", res.text == "Hello from OpenAI", res.text)
    check("openai usage parsed", res.usage and res.usage.total_tokens == 8, str(res.usage))
    check("openai finish_reason", res.finish_reason == "stop")
    acc = "".join([d async for d in op.stream(msgs)])
    check("openai stream concatenates", acc == "".join(PIECES), acc)

    print("== Ollama provider ==")
    ol = mk_ollama(base)
    res = await ol.complete(msgs)
    check("ollama complete text", res.text == "Hello from Ollama", res.text)
    check("ollama usage parsed", res.usage and res.usage.total_tokens == 8, str(res.usage))
    acc = "".join([d async for d in ol.stream(msgs)])
    check("ollama stream concatenates", acc == "".join(PIECES), acc)

    print("== Identical call signature across providers ==")
    for prov in (op, ol):
        r = await prov.complete([{"role": "user", "content": "x"}], temperature=0.0, max_tokens=10)
        check(f"{prov.name} accepts dict messages + kwargs", isinstance(r, CompletionResult))

    print("== Error mapping ==")
    for model, exc in [("err-401", AIAuthError), ("err-429", AIRateLimitError), ("err-bad", AIResponseError)]:
        try:
            await op.complete(msgs, model=model)
            check(f"{model} raises {exc.__name__}", False, "no error raised")
        except exc:
            check(f"{model} raises {exc.__name__}", True)
        except Exception as e:  # noqa: BLE001
            check(f"{model} raises {exc.__name__}", False, f"got {type(e).__name__}")

    await op.aclose()
    await ol.aclose()

    print("== Factory: env-driven switch ==")
    cfg.settings.AI_PROVIDER = "ollama"
    cfg.settings.OLLAMA_BASE_URL = base
    ai.reset()
    check("AI_PROVIDER=ollama -> OllamaProvider", ai.get_chat_provider().name == "ollama")

    cfg.settings.AI_PROVIDER = "openai"
    cfg.settings.OPENAI_API_KEY = "test"
    cfg.settings.OPENAI_BASE_URL = base + "/v1"
    cfg.settings.OPENAI_CHAT_MODEL = "gpt-x"
    ai.reset()
    prov = ai.get_chat_provider()
    check("AI_PROVIDER=openai -> OpenAIProvider", prov.name == "openai")
    # works end-to-end via the factory-built instance
    r = await prov.complete(msgs)
    check("factory-built provider completes", r.text == "Hello from OpenAI", r.text)

    print("== Factory: unknown + missing-key config errors ==")
    try:
        ai.get_chat_provider("does-not-exist")
        check("unknown provider -> AIConfigError", False)
    except AIConfigError:
        check("unknown provider -> AIConfigError", True)

    cfg.settings.AI_PROVIDER = "openai"
    cfg.settings.OPENAI_API_KEY = None
    ai.reset()
    try:
        ai.get_chat_provider()
        check("openai w/o key -> AIConfigError", False)
    except AIConfigError:
        check("openai w/o key -> AIConfigError", True)

    print("== Future provider registration ==")

    class EchoProvider(ChatProvider):
        name = "echo"

        async def complete(self, messages, **kw):
            return CompletionResult(text="echo", model="echo")

        async def stream(self, messages, **kw):
            yield "echo"

    ai.register_provider("echo", lambda: EchoProvider())
    cfg.settings.AI_PROVIDER = "echo"
    ai.reset()
    check("registered future provider usable", ai.get_chat_provider().name == "echo")
    check("echo appears in registry", "echo" in ai.available_providers())

    await ai.close_providers()


def main():
    srv, base = start_server()
    try:
        asyncio.run(run(base))
    finally:
        srv.shutdown()
    print(f"\nRESULT: {P['pass']} passed, {P['fail']} failed")
    sys.exit(1 if P["fail"] else 0)


if __name__ == "__main__":
    main()
