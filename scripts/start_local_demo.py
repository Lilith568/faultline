"""Start a private local Faultline demo; never persist or print the Meta key."""
from __future__ import annotations

import getpass
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time
from typing import Callable
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import warnings
import webbrowser


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORCED_ENV = {
    "FAULTLINE_MODEL_BACKEND": "meta",
    "META_BASE_URL": "https://api.meta.ai/v1",
    "META_MODEL": "muse-spark-1.3",
    "FAULTLINE_ALLOW_REMOTE": "0",
}


def _load_runtime():
    """Prefer this checkout even when launched from a desktop shortcut elsewhere."""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    try:
        import uvicorn
        from faultline.config import get_settings
    except ImportError:
        return None
    return uvicorn, get_settings


def _reserve_socket() -> socket.socket:
    """Keep ownership until Uvicorn takes over; leave existing services alone."""
    for port in (8000, 0):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", port))
            listener.listen(socket.SOMAXCONN)
            return listener
        except OSError:
            listener.close()
            if port == 0:
                raise
    raise OSError("No local port available")


def _open_when_ready(server, url: str, stop: threading.Event, *, timeout: float = 20.0,
                     opener=None, open_browser: Callable | None = None) -> None:
    """Only read our local server; no API key, model request or external proxy is involved."""
    opener = opener or build_opener(ProxyHandler({}))
    open_browser = open_browser or webbrowser.open
    deadline = time.monotonic() + timeout
    while not stop.is_set() and time.monotonic() < deadline:
        if not getattr(server, "started", False):
            stop.wait(0.15)
            continue
        try:
            with opener.open(url + "api/config", timeout=0.5) as response:
                config = json.loads(response.read(64_000))
            if (config.get("meta_configured") is True and config.get("backend") == "meta"
                    and config.get("model") == "muse-spark-1.3"):
                if not stop.is_set():
                    try:
                        opened = open_browser(url + "?demo=composer", new=2)
                    except Exception:
                        opened = False
                    if not opened:
                        print("Bitte diese lokale Adresse im Browser oeffnen: " + url)
                return
        except (OSError, URLError, ValueError, TypeError, AttributeError):
            pass
        stop.wait(0.15)
    if not stop.is_set():
        print("Der Browser konnte noch nicht starten. Lokale Adresse: " + url)


def _read_key() -> str | None:
    try:
        # getpass otherwise falls back to echoing stdin if a terminal cannot hide input.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("Meta API-Key (verdeckte Eingabe): ").strip()
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("Keine verdeckte Eingabe moeglich oder Eingabe abgebrochen.", file=sys.stderr)
        return None
    if not key:
        print("Kein Key eingegeben. Faultline wurde nicht gestartet.")
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in key):
        print("Der Key enthaelt ungueltige Steuerzeichen.", file=sys.stderr)
        return None
    return key


def main() -> int:
    runtime = _load_runtime()
    if runtime is None:
        print("Die Einrichtung ist noch unvollstaendig. Bitte Setup-Faultline.cmd erneut starten.", file=sys.stderr)
        return 1
    uvicorn, get_settings = runtime
    previous = dict(os.environ)
    restore_names = set(FORCED_ENV) | {"MODEL_API_KEY"}
    listener = None
    stop = threading.Event()
    browser_thread = None
    try:
        os.environ.update(FORCED_ENV)
        settings = get_settings()  # Also supports an existing, private local .env.
        restore_names.update(set(os.environ) - set(previous))
        print("Dieser Starter speichert und zeigt deinen Meta-Key nicht an.")
        print("Echte Meta-Aufrufe starten erst mit 'Start hunt' und koennen API-Guthaben verbrauchen.")
        if not settings.api_key:
            key = _read_key()
            if not key:
                return 1
            os.environ["MODEL_API_KEY"] = key
            del key
        listener = _reserve_socket()
        port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}/"
        config = uvicorn.Config("faultline.server:app", host="127.0.0.1", port=port,
                                log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        browser_thread = threading.Thread(target=_open_when_ready, args=(server, url, stop), daemon=True)
        browser_thread.start()
        print("Faultline startet unter " + url + " - mit Strg+C beenden.")
        server.run(sockets=[listener])
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        # Dependency, socket and settings errors must not echo arbitrary key-bearing values.
        print("Faultline konnte nicht starten. Bitte Setup-Faultline.cmd erneut ausfuehren.", file=sys.stderr)
        return 1
    finally:
        stop.set()
        if browser_thread is not None:
            browser_thread.join(timeout=2.0)
        if listener is not None:
            listener.close()
        # A malformed .env may have added values before settings raised an error.
        restore_names.update(set(os.environ) - set(previous))
        for name in restore_names:
            if name in previous:
                os.environ[name] = previous[name]
            else:
                os.environ.pop(name, None)


if __name__ == "__main__":
    raise SystemExit(main())
