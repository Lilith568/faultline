"""Runtime settings. Secrets stay in the environment or a local .env file."""
from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines); existing variables win."""
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    model: str
    reasoning_effort: str | None
    allow_remote: bool
    artifacts: Path

    @property
    def meta_configured(self) -> bool:
        return bool(self.api_key)


def get_settings() -> Settings:
    load_dotenv()
    effort = os.getenv("META_REASONING_EFFORT", "medium").strip() or None
    return Settings(
        api_key=os.getenv("MODEL_API_KEY") or None,
        base_url=os.getenv("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/"),
        model=os.getenv("META_MODEL", "muse-spark-1.3"),
        reasoning_effort=effort,
        allow_remote=os.getenv("FAULTLINE_ALLOW_REMOTE", "0") == "1",
        artifacts=Path(os.getenv("FAULTLINE_ARTIFACTS", str(ROOT / "artifacts"))),
    )


LOCAL_SUFFIXES = (".localhost", ".test")


_SUSPICIOUS = re.compile(r"[\\\s\x00-\x1f\x7f]")


def is_local_url(url: str) -> bool:
    """Faultline only hunts on the developer's own local app by default."""
    if _SUSPICIOUS.search(url or ""):
        return False  # backslashes, whitespace or control characters are parsed differently by browsers
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    if "@" in parsed.netloc:
        return False  # no user-info tricks such as http://evil.example@localhost/
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_target(url: str, settings: Settings) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or _SUSPICIOUS.search(url or "") or "@" in parsed.netloc:
        raise ValueError("target must be a plain http(s) URL")
    if not settings.allow_remote and not is_local_url(url):
        raise ValueError(
            "Faultline only tests local development servers (localhost, 127.0.0.1, *.localhost, *.test). "
            "Set FAULTLINE_ALLOW_REMOTE=1 only for staging sites you own."
        )
