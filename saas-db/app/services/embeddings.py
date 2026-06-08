"""Embedding generation.

Two real providers behind one interface:

* ``LocalHashingEmbedder`` — fully offline and deterministic. It uses the hashing
  trick (a.k.a. feature hashing) over word uni/bi-grams projected into a fixed
  dimensional space and L2-normalized, so cosine similarity reflects lexical
  overlap. Not a neural model, but a genuine, dependency-free embedding suitable
  for environments without network/model access. It is the default.
* ``OpenAIEmbedder`` — calls an OpenAI-compatible /embeddings endpoint. Used when
  ``EMBEDDING_PROVIDER=openai`` and an API key is configured.

Swap providers via settings; everything downstream (Qdrant, storage, search)
is dimension-driven and provider-agnostic.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx

from app.core.config import settings

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Embedder(Protocol):
    provider: str
    model: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalHashingEmbedder:
    """Deterministic offline embedder using feature hashing over n-grams."""

    provider = "local-hash"

    def __init__(self, model: str, dim: int):
        self.model = model
        self.dim = dim

    def _hash(self, token: str) -> tuple[int, float]:
        digest = hashlib.sha1(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % self.dim
        sign = 1.0 if digest[4] & 1 else -1.0
        return idx, sign

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _tokenize(text)
        if not tokens:
            # Avoid zero vectors (undefined cosine); use a stable sentinel.
            idx, sign = self._hash("\x00empty")
            vec[idx] = sign
        else:
            features = list(tokens)
            features += [
                f"{a}_{b}" for a, b in zip(tokens, tokens[1:])
            ]  # bigrams add a little word-order signal
            for feat in features:
                idx, sign = self._hash(feat)
                vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class OpenAIEmbedder:
    """Embedder backed by an OpenAI-compatible embeddings endpoint."""

    provider = "openai"

    def __init__(self, model: str, dim: int, api_key: str, base_url: str):
        self.model = model
        self.dim = dim
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = httpx.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self.model, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        # Preserve input order.
        ordered = sorted(data, key=lambda d: d["index"])
        return [d["embedding"] for d in ordered]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is not None:
        return _embedder
    if settings.EMBEDDING_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is unset")
        _embedder = OpenAIEmbedder(
            model=settings.OPENAI_EMBED_MODEL,
            dim=settings.EMBEDDING_DIM,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
    else:
        _embedder = LocalHashingEmbedder(
            model=settings.EMBEDDING_MODEL, dim=settings.EMBEDDING_DIM
        )
    return _embedder
