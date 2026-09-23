"""Optional embedding generation for judgment cases."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self, *, model: str = "text-embedding-3-small") -> None:
        self.model = model

    async def embed(self, text: str) -> list[float] | None:
        if not text.strip():
            return None
        api_key = settings.openai_api_key or settings.deepseek_api_key
        if not api_key:
            logger.debug("No embedding API key configured; skipping embedding")
            return None

        base_url = settings.openai_base_url.rstrip("/")
        url = f"{base_url}/embeddings"
        headers = {"Authorization": f"Bearer {api_key}"}
        body: dict[str, Any] = {"model": self.model, "input": text[:8000]}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                data = response.json()
            vector = data["data"][0]["embedding"]
            return [float(x) for x in vector]
        except Exception:
            logger.exception("Embedding API call failed")
            return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
