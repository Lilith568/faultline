"""The local launcher never persists a key or starts a model call by itself."""
from __future__ import annotations

import importlib.util
import io
import json
import os
from pathlib import Path
import socket
from types import SimpleNamespace
import threading
import warnings

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "start_local_demo.py"
spec = importlib.util.spec_from_file_location("faultline_local_demo", SOURCE)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class Listener:
    closed = False

    def getsockname(self):
        return "127.0.0.1", 8123

    def close(self):
        self.closed = True


def runtime(monkeypatch, *, key=None, fail=False, added_env=None):
    calls = []
    listener = Listener()

    def settings():
        if added_env:
            os.environ.update(added_env)
        return SimpleNamespace(api_key=key)

    class Uvicorn:
        @staticmethod
        def Config(app, **kwargs):
            calls.append((app, kwargs))
            return kwargs

        class Server:
            def __init__(self, config):
                self.started = False

            def run(self, *, sockets):
                assert sockets == [listener]
                assert os.environ["MODEL_API_KEY"] == (key or "private-launcher-test-key")
                assert os.environ["META_BASE_URL"] == "https://api.meta.ai/v1"
                assert os.environ["FAULTLINE_ALLOW_REMOTE"] == "0"
                if fail:
                    raise RuntimeError("Never echo private-launcher-test-key")

    monkeypatch.setattr(demo, "_load_runtime", lambda: (Uvicorn, settings))
    monkeypatch.setattr(demo, "_reserve_socket", lambda: listener)
    monkeypatch.setattr(demo, "_open_when_ready", lambda *args: None)
    return calls, listener


def test_prompted_key_is_private_and_environment_is_restored(monkeypatch, capsys):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("META_BASE_URL", "https://previous.example")
    monkeypatch.setenv("FAULTLINE_ALLOW_REMOTE", "1")
    calls, listener = runtime(monkeypatch, added_env={"FAULTLINE_DOTENV_TEST": "private-value"})
    monkeypatch.setattr(demo.getpass, "getpass", lambda prompt: "private-launcher-test-key")
    previous = dict(os.environ)
    assert demo.main() == 0
    assert dict(os.environ) == previous
    assert listener.closed
    assert calls[0][0] == "faultline.server:app"
    assert calls[0][1]["host"] == "127.0.0.1"
    assert calls[0][1]["access_log"] is False
    assert "private-launcher-test-key" not in str(capsys.readouterr())


def test_existing_key_is_not_requested_or_changed(monkeypatch, capsys):
    monkeypatch.setenv("MODEL_API_KEY", "existing-private-test-key")
    runtime(monkeypatch, key="existing-private-test-key")
    monkeypatch.setattr(demo.getpass, "getpass", lambda prompt: pytest.fail("Existing key was requested again"))
    assert demo.main() == 0
    assert os.environ["MODEL_API_KEY"] == "existing-private-test-key"
    assert "existing-private-test-key" not in str(capsys.readouterr())


def test_failed_server_restores_key_and_does_not_echo_exception(monkeypatch, capsys):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    _, listener = runtime(monkeypatch, fail=True)
    monkeypatch.setattr(demo.getpass, "getpass", lambda prompt: "private-launcher-test-key")
    previous = dict(os.environ)
    assert demo.main() == 1
    assert dict(os.environ) == previous
    assert listener.closed
    output = str(capsys.readouterr())
    assert "private-launcher-test-key" not in output
    assert "konnte nicht starten" in output


@pytest.mark.parametrize("value", ["", " \t ", "key\rcontrol"])
def test_empty_or_control_key_never_starts_server(monkeypatch, value):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    runtime(monkeypatch)
    monkeypatch.setattr(demo.getpass, "getpass", lambda prompt: value)
    monkeypatch.setattr(demo, "_reserve_socket", lambda: pytest.fail("Server started without a valid input key"))
    assert demo.main() == 1
    assert "MODEL_API_KEY" not in os.environ


def test_getpass_cannot_fall_back_to_echoed_input(monkeypatch, capsys):
    def insecure_getpass(prompt):
        warnings.warn("Cannot hide input", demo.getpass.GetPassWarning)
        pytest.fail("getpass continued after its echo warning")

    monkeypatch.setattr(demo.getpass, "getpass", insecure_getpass)
    assert demo._read_key() is None
    assert "Keine verdeckte Eingabe" in capsys.readouterr().err


def test_missing_dependencies_have_actionable_message(monkeypatch, capsys):
    monkeypatch.setattr(demo, "_load_runtime", lambda: None)
    assert demo.main() == 1
    assert "Setup-Faultline.cmd" in capsys.readouterr().err


def test_invalid_settings_restore_partially_loaded_dotenv(monkeypatch):
    def settings():
        os.environ["FAULTLINE_PARTIAL_DOTENV_TEST"] = "private-local-value"
        raise ValueError("Invalid local configuration")

    monkeypatch.setattr(demo, "_load_runtime", lambda: (SimpleNamespace(), settings))
    previous = dict(os.environ)
    assert demo.main() == 1
    assert dict(os.environ) == previous


def test_busy_default_port_is_left_alone():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as existing:
        try:
            existing.bind(("127.0.0.1", 8000))
        except OSError:
            pytest.skip("Another local process already owns port 8000")
        existing.listen()
        listener = demo._reserve_socket()
        try:
            assert listener.getsockname()[0] == "127.0.0.1"
            assert listener.getsockname()[1] != 8000
            assert existing.fileno() >= 0
        finally:
            listener.close()


def test_browser_waits_for_our_ready_server_and_reads_only_local_config():
    opened = []
    requests = []
    config = {"meta_configured": True, "backend": "meta", "model": "muse-spark-1.3"}

    class Opener:
        def open(self, url, *, timeout):
            requests.append((url, timeout))
            return io.BytesIO(json.dumps(config).encode())

    demo._open_when_ready(SimpleNamespace(started=True), "http://127.0.0.1:8123/", threading.Event(),
                          opener=Opener(), open_browser=lambda url, new: opened.append((url, new)) or True)
    assert requests == [("http://127.0.0.1:8123/api/config", 0.5)]
    assert opened == [("http://127.0.0.1:8123/?demo=composer", 2)]


def test_stopped_server_does_not_open_browser_or_request_anything():
    stop = threading.Event()
    stop.set()

    class Opener:
        def open(self, *args, **kwargs):
            pytest.fail("Requested a server after shutdown")

    demo._open_when_ready(SimpleNamespace(started=True), "http://127.0.0.1:8123/", stop,
                          opener=Opener(), open_browser=lambda *args, **kwargs: pytest.fail("Opened after shutdown"))
