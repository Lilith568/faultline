import socket
import threading
import time
import urllib.request

import pytest
import uvicorn


@pytest.fixture(scope="session")
def server_url():
    """Run the Faultline server (with the demo apps) in a background thread."""
    from faultline.server import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(80):
        try:
            urllib.request.urlopen(url + "/api/config", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    yield url
    server.should_exit = True
    thread.join(timeout=5)
