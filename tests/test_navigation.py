"""Navigation redirects must not contact an origin outside the local test target."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import async_playwright

from faultline.discover import guard_navigation, origin_of


@pytest.mark.asyncio
async def test_navigation_guard_blocks_redirect_before_destination_and_preserves_local_page():
    destination_requests = []

    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            destination_requests.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<title>Other origin</title>")

        def log_message(self, *args):
            pass

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)
    other_origin = f"http://127.0.0.1:{destination.server_port}"

    class Target(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", other_origin + "/escaped")
                self.end_headers()
                return
            body = b"<!doctype html><title>Local target</title><input aria-label='Draft'>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    target = ThreadingHTTPServer(("127.0.0.1", 0), Target)
    target_url = f"http://127.0.0.1:{target.server_port}"
    workers = [threading.Thread(target=server.serve_forever, daemon=True) for server in (target, destination)]
    for worker in workers:
        worker.start()
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            try:
                context = await browser.new_context(service_workers="block")
                await guard_navigation(context, origin_of(target_url))
                page = await context.new_page()
                await page.goto(target_url + "/normal")
                assert await page.title() == "Local target"
                await page.get_by_label("Draft").fill("Synthetic draft")
                assert await page.get_by_label("Draft").input_value() == "Synthetic draft"
                with pytest.raises(Exception, match="net::ERR_"):
                    await page.goto(target_url + "/redirect")
                assert destination_requests == [], "Blocking after navigation would still leak a network request"
                await page.close()
                page = await context.new_page()
                with pytest.raises(Exception, match="net::ERR_"):
                    await page.goto(other_origin + "/direct")
                assert destination_requests == []
                await page.close()
                page = await context.new_page()
                await page.goto(target_url + "/normal")
                assert await page.title() == "Local target"
                await context.close()
            finally:
                await browser.close()
    finally:
        for server in (target, destination):
            server.shutdown()
            server.server_close()
        for worker in workers:
            worker.join(timeout=2)
