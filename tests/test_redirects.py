"""Navigation follows same-origin redirects and never contacts another origin through a redirect."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import async_playwright

from faultline.discover import guard_navigation, origin_of


def _serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(scope="module")
def sites():
    contacted = {"other": 0, "posts": 0}

    class Other(BaseHTTPRequestHandler):
        def do_GET(self):
            contacted["other"] += 1
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"other origin")

        def log_message(self, *args):
            pass

    other = _serve(Other)
    other_url = f"http://127.0.0.1:{other.server_port}"

    class App(BaseHTTPRequestHandler):
        def do_GET(self):
            hops = {"/": "/step", "/step": "/app", "/hop": "/escape", "/escape": other_url + "/x"}
            if self.path in hops:
                return self._redirect(hops[self.path])
            saved = "saved" if "saved" in self.path else ""
            body = (f"<!doctype html><p id=s>{saved}</p><p id=c>{self.headers.get('Cookie', '')}</p>"
                    "<form method=post action=/save><input aria-label=Name name=n><button>Save</button></form>")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(body.encode())

        def do_POST(self):
            contacted["posts"] += 1
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self._redirect("/app?saved=1", 303, cookie="flash=ok; Path=/")

        def _redirect(self, location, status=302, cookie=None):
            self.send_response(status)
            self.send_header("Location", location)
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    app = _serve(App)
    yield f"http://127.0.0.1:{app.server_port}", contacted
    app.shutdown()
    other.shutdown()


async def _page(browser, base):
    context = await browser.new_context()
    await guard_navigation(context, origin_of(base))
    return context, await context.new_page()


@pytest.mark.asyncio
async def test_same_origin_redirects_and_post_redirect_get_work(sites):
    base, contacted = sites
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context, page = await _page(browser, base)
        await page.goto(base + "/")
        assert page.url == base + "/app"
        await page.get_by_label("Name").fill("Ada")
        await page.get_by_role("button", name="Save").click()
        await page.wait_for_url(base + "/app?saved=1")
        assert await page.locator("#s").text_content() == "saved"
        assert "flash=ok" in await page.locator("#c").text_content()
        assert contacted["posts"] == 1, "the form is submitted exactly once"
        await browser.close()


@pytest.mark.asyncio
async def test_redirect_chain_to_another_origin_is_blocked_before_contact(sites):
    base, contacted = sites
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context, page = await _page(browser, base)
        with pytest.raises(Exception, match="ERR_BLOCKED_BY_CLIENT"):
            await page.goto(base + "/hop")
        assert contacted["other"] == 0
        await browser.close()
