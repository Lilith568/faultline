"""Small Meta Model API client (OpenAI-compatible Chat Completions).

Uses structured output (JSON schema) and records every call so reports can show
which model did what, how long it took and how many tokens it used.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .config import Settings


class MetaError(RuntimeError):
    pass


class MetaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.api_key:
            raise MetaError("MODEL_API_KEY is not set")
        self.settings = settings
        self.model = settings.model
        self.calls: list[dict] = []
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=httpx.Timeout(120.0, connect=15.0),
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def json_call(self, *, purpose: str, system: str, user: Any, schema_name: str,
                        schema: dict, image_png: bytes | None = None) -> dict:
        """Call the model and return parsed JSON that matches `schema`."""
        text = user if isinstance(user, str) else json.dumps(user, ensure_ascii=False)
        content: Any = text
        if image_png:
            import base64
            content = [
                {"type": "text", "text": text},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + base64.b64encode(image_png).decode()}},
            ]
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
        }
        if self.settings.reasoning_effort:
            body["reasoning_effort"] = self.settings.reasoning_effort

        last_error = "unknown error"
        for attempt in range(3):
            started = time.monotonic()
            try:
                response = await self._client.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            elapsed = round(time.monotonic() - started, 2)
            if response.status_code == 400 and body["response_format"]["json_schema"].get("strict"):
                # Fall back to non-strict structured output if the strict schema is refused.
                body["response_format"]["json_schema"]["strict"] = False
                last_error = f"HTTP 400 with strict schema: {response.text[:200]}"
                continue
            if response.status_code == 400 and "reasoning_effort" in body:
                body.pop("reasoning_effort")
                last_error = f"HTTP 400: {response.text[:200]}"
                continue
            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code in (401, 403, 404):
                    break
                continue
            payload = response.json()
            usage = payload.get("usage") or {}
            self.calls.append({"purpose": purpose, "model": payload.get("model", self.model),
                               "seconds": elapsed,
                               "input_tokens": usage.get("prompt_tokens"),
                               "output_tokens": usage.get("completion_tokens")})
            try:
                message = payload["choices"][0]["message"]
                return _parse_json(message.get("content") or "")
            except (KeyError, IndexError, ValueError) as exc:
                last_error = f"unparseable model output: {exc}"
                continue
        raise MetaError(last_error)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])
