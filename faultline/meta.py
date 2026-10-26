"""Meta Muse HTTP client with structured output and an audit record for every attempt.

The wire format is Chat Completions. No OpenAI SDK, service, or model is used.
Remote error bodies and transport exception messages are deliberately not logged:
providers can echo credentials, source code, and request contents in them.
"""
from __future__ import annotations

import json
import time
from typing import Any

import httpx

from .config import META_MODELS, META_OPEN_MODELS, Settings, validate_model_settings


class MetaError(RuntimeError):
    pass


class MetaClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        try:
            validate_model_settings(settings, test_transport=transport is not None)
        except ValueError as exc:
            raise MetaError(str(exc)) from exc
        if not settings.meta_configured:
            raise MetaError("MODEL_API_KEY is not set" if settings.backend == "meta"
                            else "META_OPEN_API_KEY is required for a remote Meta model deployment")
        self.settings = settings
        self.model = settings.model
        self.calls: list[dict] = []
        headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
        self._client = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/") + "/", headers=headers,
            timeout=httpx.Timeout(120.0, connect=15.0), transport=transport,
            follow_redirects=False,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def json_call(self, *, purpose: str, system: str, user: Any, schema_name: str,
                        schema: dict, image_png: bytes | None = None) -> dict:
        """Return a JSON object; domain validators still enforce the closed vocabulary."""
        text = user if isinstance(user, str) else json.dumps(user, ensure_ascii=False)
        content: Any = text
        if image_png and self.settings.supports_vision:
            import base64
            content = [
                {"type": "text", "text": text},
                {"type": "image_url",
                 "image_url": {"url": "data:image/png;base64," + base64.b64encode(image_png).decode()}},
            ]
        if self.settings.json_mode == "json_schema":
            response_format = {"type": "json_schema", "json_schema": {
                "name": schema_name, "schema": schema, "strict": True}}
        else:
            response_format = {"type": "json_object"}
            system += "\nReturn only a JSON object matching this schema:\n" + json.dumps(schema)
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
            "response_format": response_format,
        }
        if self.settings.reasoning_effort:
            body["reasoning_effort"] = self.settings.reasoning_effort

        last_error = "Meta request did not complete"
        for attempt in range(1, 4):
            started = time.monotonic()
            audit: dict[str, Any] = {
                "purpose": purpose, "model": self.model, "backend": self.settings.backend,
                "attempt": attempt, "seconds": 0.0, "success": False,
                "input_tokens": None, "output_tokens": None,
                "image_sent": bool(image_png and self.settings.supports_vision),
            }
            self.calls.append(audit)
            try:
                response = await self._client.post("chat/completions", json=body)
            except httpx.HTTPError as exc:
                audit.update(status="transport_error", error_code=type(exc).__name__,
                             seconds=round(time.monotonic() - started, 2))
                last_error = f"Meta transport error ({type(exc).__name__})"
                continue
            audit.update(http_status=response.status_code, seconds=round(time.monotonic() - started, 2))
            if response.status_code >= 300:
                audit.update(status="http_error", error_code=f"http_{response.status_code}")
                last_error = f"Meta endpoint returned HTTP {response.status_code}"
                structured = body["response_format"].get("json_schema", {})
                if response.status_code == 400 and structured.get("strict"):
                    structured["strict"] = False
                    continue
                if response.status_code == 400 and "reasoning_effort" in body:
                    body.pop("reasoning_effort")
                    continue
                if response.status_code in (401, 403, 404) or 300 <= response.status_code < 400:
                    break
                continue
            try:
                payload = response.json()
                usage = payload.get("usage") or {}
                for output, name in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
                    value = usage.get(name)
                    audit[output] = value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None
                reported = payload.get("model", self.model)
                if reported not in META_MODELS | META_OPEN_MODELS:
                    raise ValueError("endpoint reported a model outside the Meta allowlist")
                audit["reported_model"] = reported
                if reported != self.model:
                    raise ValueError("endpoint reported a different model from the requested model")
                message = payload["choices"][0]["message"]
                parsed = _parse_json(message.get("content") or "")
                if not isinstance(parsed, dict):
                    raise ValueError("model output is not a JSON object")
                audit.update(status="success", success=True)
                return parsed
            except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
                audit.update(status="invalid_output", error_code=type(exc).__name__)
                last_error = f"Unparseable Meta model output ({type(exc).__name__})"
        raise MetaError(last_error)


def _parse_json(text: str) -> dict:
    text = text.strip()
    if len(text) > 2_000_000:
        raise ValueError("model output exceeds the response limit")
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start:end + 1])
