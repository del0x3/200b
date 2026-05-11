"""Thin async HTTP client around the DeepSeek chat-completions API."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatMessage:
    """A single chat-completions message: role + text content."""

    role: str
    content: str

    def to_dict(self) -> dict[str, str]:
        """Serialise to the wire format expected by DeepSeek."""
        return {"role": self.role, "content": self.content}


class DeepSeekError(Exception):
    """Raised on any non-recoverable failure talking to DeepSeek."""


class DeepSeekClient:
    """Lazily-opened async HTTP client for `POST /v1/chat/completions`.

    Holds a single `httpx.AsyncClient` for the lifetime of the FastAPI
    process. Retries once on transient errors before raising.
    """

    BASE_URL: str = "https://api.deepseek.com"
    MODEL: str = "deepseek-chat"
    DEFAULT_TIMEOUT: float = 30.0

    def __init__(self, api_key: str, *, model: str | None = None, timeout: float | None = None) -> None:
        self._api_key: str = api_key
        self._model: str = model or self.MODEL
        self._timeout: float = timeout or self.DEFAULT_TIMEOUT
        self._client: httpx.AsyncClient | None = None

    async def open(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int = 300,
    ) -> str:
        if self._client is None:
            raise DeepSeekError("client is not opened")
        if not self._api_key:
            raise DeepSeekError("DEEPSEEK_API_KEY is not set")

        payload: dict[str, object] = {
            "model": self._model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                response = await self._client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()
                data: dict[str, object] = response.json()
                choices = data.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise DeepSeekError("empty choices in response")
                message = choices[0].get("message") if isinstance(choices[0], dict) else None
                if not isinstance(message, dict):
                    raise DeepSeekError("malformed message in response")
                content = message.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise DeepSeekError("empty content")
                return content.strip()
            except (httpx.HTTPError, DeepSeekError) as exc:
                last_exc = exc
                logger.warning("DeepSeek call failed (attempt %d): %s", attempt + 1, exc)
        raise DeepSeekError(f"DeepSeek call failed after retries: {last_exc}")
