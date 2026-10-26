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
    backend: str = "meta"
    supports_vision: bool = True
    json_mode: str = "json_schema"

    @property
    def meta_configured(self) -> bool:
        return bool(self.api_key) or (self.backend == "open_weights" and is_local_url(self.base_url))


def get_settings() -> Settings:
    load_dotenv()
    backend = os.getenv("FAULTLINE_MODEL_BACKEND", "meta").strip()
    if backend not in ("meta", "open_weights"):
        raise ValueError("FAULTLINE_MODEL_BACKEND must be meta or open_weights")
    open_weights = backend == "open_weights"
    prefix = "META_OPEN_" if open_weights else "META_"
    effort = os.getenv(prefix + "REASONING_EFFORT", "" if open_weights else "medium").strip() or None
    return Settings(
        api_key=os.getenv("META_OPEN_API_KEY" if open_weights else "MODEL_API_KEY") or None,
        base_url=os.getenv(prefix + "BASE_URL", "http://127.0.0.1:11434/v1" if open_weights
                           else "https://api.meta.ai/v1").rstrip("/"),
        model=os.getenv(prefix + "MODEL", "muse-glimmer" if open_weights else "muse-spark-1.3"),
        reasoning_effort=effort,
        allow_remote=os.getenv("FAULTLINE_ALLOW_REMOTE", "0") == "1",
        artifacts=Path(os.getenv("FAULTLINE_ARTIFACTS", str(ROOT / "artifacts"))),
        backend=backend,
        supports_vision=not open_weights or os.getenv("META_OPEN_VISION", "0") == "1",
        json_mode=os.getenv("META_OPEN_JSON_MODE", "json_schema") if open_weights else "json_schema",
    )


# Exact published model IDs; endpoint compatibility does not permit another provider's model.
META_MODELS = frozenset({"muse-spark-1.3", "muse-wonder-1.0"})
META_OPEN_MODELS = frozenset({
    "muse-glimmer", "meta-models/Muse-Glimmer-30B",
    "meta-models/Muse-Spark-Open-816B-A42B",
    "meta-models/Muse-Spark-Open-816B-A42B-NVFP4",
    "meta/muse-spark-open",
    "meta-models/muse-spark-open-1026",
})


def validate_model_settings(settings: Settings, *, test_transport: bool = False) -> None:
    """Refuse unknown model families and credential-bearing or insecure endpoint URLs."""
    allowed = META_MODELS if settings.backend == "meta" else META_OPEN_MODELS
    if settings.backend not in ("meta", "open_weights") or settings.model not in allowed:
        raise ValueError("Only the documented Meta Muse models are supported by this backend")
    parsed = urlparse(settings.base_url)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or _SUSPICIOUS.search(settings.base_url)):
        raise ValueError("Model endpoint must be a plain HTTP(S) base URL without credentials or query parameters")
    if parsed.scheme != "https" and not is_local_url(settings.base_url):
        raise ValueError("Remote model endpoints require HTTPS")
    if settings.backend == "meta" and parsed.hostname != "api.meta.ai" and not test_transport:
        raise ValueError("The meta backend requires api.meta.ai; use open_weights for a Meta model deployment")
    if parsed.hostname.lower().endswith(("openai.com", "anthropic.com")):
        raise ValueError("Only Meta model deployments are supported")
    if settings.json_mode not in ("json_schema", "json_object"):
        raise ValueError("Model JSON mode must be json_schema or json_object")
    if settings.reasoning_effort not in (None, "none", "minimal", "low", "medium", "high", "xhigh"):
        raise ValueError("Unknown Meta reasoning effort")


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
