"""Embedding providers behind one interface.

`HashEmbedder` is a deterministic bag-of-words hash: no network, no key, stable
across runs. It is what the tests use and what the app falls back to when no key
is set, so scoped retrieval works end to end without a provider. `VoyageEmbedder`
is the production choice (Anthropic's recommended embedding partner).
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Protocol

import httpx

from enola.core.config import get_settings
from enola.core.errors import AgentUnavailableError
from enola.core.models.documents import EMBEDDING_DIM

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int

    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbedder:
    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = _TOKEN.findall(text.lower())
        # Unigrams plus bigrams so word order contributes a little.
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        for gram in grams:
            digest = hashlib.blake2b(gram.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[index] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


class VoyageEmbedder:
    url = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, api_key: str, model: str = "voyage-3.5", dim: int = EMBEDDING_DIM) -> None:
        if not api_key:
            raise AgentUnavailableError("VOYAGE_API_KEY is not set.")
        self.api_key = api_key
        self.model = model
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), 64):
            batch = list(texts[start : start + 64])
            response = httpx.post(
                self.url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": batch, "model": self.model, "output_dimension": self.dim},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()["data"]
            out.extend([item["embedding"] for item in sorted(data, key=lambda d: d["index"])])
        return out


def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedder == "voyage":
        return VoyageEmbedder(settings.voyage_api_key, dim=settings.embedding_dim)
    return HashEmbedder(settings.embedding_dim)
