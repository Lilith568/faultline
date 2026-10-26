"""Load explicitly supplied Playwright state without putting credentials in reports."""
from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urlsplit

MAX_STATE_BYTES = 1024 * 1024
MAX_ITEMS = 500
MAX_VALUE_CHARS = 65536


def canonical_origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Storage state requires a plain http(s) target origin")
    host = parsed.hostname.lower()
    host = f"[{host}]" if ":" in host else host
    port = parsed.port
    default = 80 if parsed.scheme == "http" else 443
    return f"{parsed.scheme}://{host}" + (f":{port}" if port and port != default else "")


def _text(value, field: str) -> str:
    if not isinstance(value, str) or len(value) > MAX_VALUE_CHARS:
        raise ValueError(f"Invalid storage state {field}")
    return value


def scope_storage_state(state: dict, target_url: str) -> dict:
    """Retain cookies for the exact target host and localStorage for its exact origin.

    Browser cookies are host scoped, not port scoped. Authenticated contexts also
    reject cross-origin requests. State is never inserted into model input.
    IndexedDB and sessionStorage are intentionally not imported.
    """
    if not isinstance(state, dict):
        raise ValueError("Storage state must be a JSON object")
    try:
        size = len(json.dumps(state, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("Storage state is not valid JSON") from exc
    if size > MAX_STATE_BYTES:
        raise ValueError("Storage state exceeds the size limit")
    cookies, origins = state.get("cookies", []), state.get("origins", [])
    if not isinstance(cookies, list) or not isinstance(origins, list) or max(len(cookies), len(origins)) > MAX_ITEMS:
        raise ValueError("Invalid storage state collections")
    origin = canonical_origin(target_url)
    host = urlsplit(origin).hostname
    kept_cookies, kept_origins = [], []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            raise ValueError("Invalid storage state cookie")
        domain = cookie.get("domain")
        if not isinstance(domain, str):
            raise ValueError("Invalid storage state cookie domain")
        if domain.lower().lstrip(".") != host:
            continue
        name, value = _text(cookie.get("name"), "cookie name"), _text(cookie.get("value"), "cookie value")
        path = cookie.get("path", "/")
        expires = cookie.get("expires", -1)
        same_site = cookie.get("sameSite", "Lax")
        if not name or any(ord(c) < 33 or c in ";=" for c in name):
            raise ValueError("Invalid storage state cookie name")
        if not isinstance(path, str) or not path.startswith("/") or len(path) > 2048:
            raise ValueError("Invalid storage state cookie path")
        if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not math.isfinite(expires):
            raise ValueError("Invalid storage state cookie expiry")
        if same_site not in ("Strict", "Lax", "None"):
            raise ValueError("Invalid storage state cookie sameSite")
        if not isinstance(cookie.get("httpOnly", False), bool) or not isinstance(cookie.get("secure", False), bool):
            raise ValueError("Invalid storage state cookie flags")
        kept_cookies.append({"name": name, "value": value, "domain": host, "path": path,
                             "expires": expires, "httpOnly": cookie.get("httpOnly", False),
                             "secure": cookie.get("secure", False), "sameSite": same_site})
    for item in origins:
        if not isinstance(item, dict) or not isinstance(item.get("origin"), str):
            raise ValueError("Invalid storage state origin")
        try:
            matches = canonical_origin(item["origin"]) == origin
        except ValueError:
            matches = False
        if not matches:
            continue
        values = item.get("localStorage", [])
        if not isinstance(values, list) or len(values) > MAX_ITEMS:
            raise ValueError("Invalid storage state localStorage")
        safe_values = []
        for entry in values:
            if not isinstance(entry, dict):
                raise ValueError("Invalid storage state localStorage entry")
            safe_values.append({"name": _text(entry.get("name"), "localStorage name"),
                                "value": _text(entry.get("value"), "localStorage value")})
        if safe_values:
            kept_origins.append({"origin": origin, "localStorage": safe_values})
    if not kept_cookies and not kept_origins:
        raise ValueError("Storage state has no cookies or localStorage for this target")
    return {"cookies": kept_cookies, "origins": kept_origins}


def load_storage_state(path: str | Path | dict | None, target_url: str) -> dict | None:
    """Read a bounded local state file. Errors never include its credential values."""
    if path is None:
        return None
    if isinstance(path, dict):
        return scope_storage_state(path, target_url)
    try:
        with Path(path).open("rb") as handle:
            raw = handle.read(MAX_STATE_BYTES + 1)
    except OSError as exc:
        raise ValueError("Cannot read the storage state file") from exc
    if len(raw) > MAX_STATE_BYTES:
        raise ValueError("Storage state exceeds the size limit")
    try:
        state = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ValueError("Storage state must contain valid JSON") from exc
    return scope_storage_state(state, target_url)


async def install_authenticated_transport(context) -> None:
    """Prevent redirect and WebSocket credential forwarding in signed-in runs.

    Register before the perturbation and origin-guard routes. Buffer ordinary
    HTTP responses and reject redirects rather than following unchecked hops.
    Authenticated streaming/WebSocket apps are not supported by this transport.
    """
    async def transport(route):
        response = None
        try:
            response = await route.fetch(max_redirects=0, timeout=10000)
            if 300 <= response.status < 400 and response.headers.get("location"):
                await route.abort("blockedbyclient")
            else:
                await route.fulfill(response=response)
        except Exception:
            try:
                await route.abort("failed")
            except Exception:
                pass  # context may have closed while an injected delay was pending
        finally:
            if response is not None:
                await response.dispose()

    async def reject_socket(route):
        await route.close(code=1008, reason="WebSockets are disabled in authenticated hunts")

    await context.route("**/*", transport)
    await context.route_web_socket("**/*", reject_socket)
