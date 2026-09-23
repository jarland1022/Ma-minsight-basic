"""LLM client with chat completions and native tool calling."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.redis import get_redis
from app.llm.schemas import ChatCompletionResult, TokenUsage, ToolCallRequest

logger = logging.getLogger(__name__)

LLM_CACHE_TTL = 86400


class LLMClient:
    def __init__(self) -> None:
        self.api_key = settings.deepseek_api_key
        self.model = settings.deepseek_model
        self.base_url = settings.deepseek_base_url.rstrip("/")

    async def chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = "auto",
        model: str | None = None,
        temperature: float = 0.0,
    ) -> ChatCompletionResult:
        if not self.api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        message = choice.get("message") or {}
        usage_raw = data.get("usage") or {}
        usage = TokenUsage(
            prompt_tokens=int(usage_raw.get("prompt_tokens") or 0),
            completion_tokens=int(usage_raw.get("completion_tokens") or 0),
        )

        tool_calls: list[ToolCallRequest] = []
        for item in message.get("tool_calls") or []:
            fn = item.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                arguments = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
            except json.JSONDecodeError:
                arguments = {}
            tool_calls.append(
                ToolCallRequest(
                    id=str(item.get("id") or ""),
                    name=str(fn.get("name") or ""),
                    arguments=arguments if isinstance(arguments, dict) else {},
                )
            )

        return ChatCompletionResult(
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=usage,
            raw_message=message,
        )

    async def complete(self, prompt: str) -> str:
        result = await self.chat(messages=[{"role": "user", "content": prompt}])
        return result.content or ""

    @staticmethod
    def parse_score(content: str) -> float:
        try:
            payload = json.loads(content)
            if isinstance(payload, dict) and "score" in payload:
                return float(max(0.0, min(100.0, float(payload["score"]))))
        except json.JSONDecodeError:
            pass
        match = re.search(r"\b(\d{1,3})\b", content)
        if match:
            return float(max(0.0, min(100.0, int(match.group(1)))))
        return 50.0

    async def get_cached_score(self, cache_key: str) -> float | None:
        try:
            redis = await get_redis()
            raw = await redis.get(cache_key)
            if raw is None:
                return None
            payload: dict[str, Any] = json.loads(raw)
            return float(payload.get("score", 50.0))
        except Exception:
            logger.debug("LLM cache read failed", exc_info=True)
            return None

    async def set_cached_score(self, cache_key: str, score: float) -> None:
        try:
            redis = await get_redis()
            await redis.set(cache_key, json.dumps({"score": score}), ex=LLM_CACHE_TTL)
        except Exception:
            logger.debug("LLM cache write failed", exc_info=True)
