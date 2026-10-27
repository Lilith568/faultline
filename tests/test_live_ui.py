"""Live-mode boundaries and visible API evidence, using only deterministic test doubles."""
from __future__ import annotations

import asyncio
import json
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.async_api import async_playwright, expect

from faultline import server
from faultline.config import Settings


HUNT_ID = "20261027-120000-abcdef"


def settings(tmp_path, *, configured=True):
    return Settings("ui-server-test-secret" if configured else None, "https://api.meta.ai/v1",
                    "muse-spark-1.3", "medium", False, tmp_path)


def report(url, *, planner="meta", required=True):
    return {
        "id": HUNT_ID, "url": url,
        "status": "complete",
        "planner": {"used": planner, "model": "muse-spark-1.3", "fallback_reason": None},
        "rounds": [], "counterexamples": [], "unconfirmed": [],
        "stats": {"browser_runs": 0, "meta_calls": 1 if required else 0, "duration_s": 0.2},
        "live_api": {"required": required, "status": "complete" if required else "not_requested",
                     "network_successes": 1 if required else 0, "calls": [{
                         "purpose": "plan", "schema_name": "faultline_plan", "model": "muse-spark-1.3",
                         "reported_model": "muse-spark-1.3-2026-10-20", "success": True,
                         "status": "success", "transport": "injected", "http_status": 200,
                         "started_at": "2026-10-27T12:00:00+00:00", "seconds": 0.2,
                         "input_tokens": 120, "output_tokens": 30,
                     }] if required else []},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("planner", ["heuristic", "recorded"])
async def test_strict_mode_refuses_non_live_planners(planner):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as client:
        response = await client.post("/api/hunts", json={"url": "http://localhost:8000/demo/composer.html",
                                                       "planner": planner, "require_live": True})
    assert response.status_code == 400
    assert "not live API runs" in response.json()["detail"]


@pytest.mark.asyncio
async def test_strict_mode_missing_key_has_server_side_setup_guidance(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "get_settings", lambda: settings(tmp_path, configured=False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as client:
        response = await client.post("/api/hunts", json={"url": "http://localhost:8000/demo/profile.html",
                                                       "planner": "meta", "require_live": True})
        public_config = (await client.get("/api/config")).json()
    assert response.status_code == 400
    assert "MODEL_API_KEY" in response.json()["detail"] and ".env" in response.json()["detail"]
    assert "Keep the key on the server" in response.json()["detail"]
    assert "api_key" not in public_config


@pytest.mark.asyncio
async def test_strict_flag_is_forwarded_and_error_report_can_be_downloaded(monkeypatch, tmp_path):
    seen = []

    class FailingHunt:
        def __init__(self, url, **kwargs):
            seen.append(kwargs)
            self.id = HUNT_ID
            self.report = report(url)
            self.report.update(status="error", error="Meta endpoint returned HTTP 401")
            self.report["live_api"].update(status="incomplete", network_successes=0)
            self.report["live_api"]["calls"][0].update(success=False, http_status=401, status="http_error")

        async def run(self):
            raise RuntimeError("Meta endpoint returned HTTP 401")

    monkeypatch.setattr(server, "Hunt", FailingHunt)
    monkeypatch.setattr(server, "get_settings", lambda: settings(tmp_path))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as client:
            response = await client.post("/api/hunts", json={"url": "http://localhost:8000/demo/profile.html",
                                                           "planner": "meta", "require_live": True})
            assert response.status_code == 200
            await asyncio.sleep(0)
            state = (await client.get(f"/api/hunts/{HUNT_ID}")).json()
            downloaded = await client.get(f"/api/hunts/{HUNT_ID}/report")
            invalid = await client.get("/api/hunts/not-a-valid-id/report")
            saved = tmp_path / HUNT_ID / "report.json"
            saved.parent.mkdir()
            saved.write_text(json.dumps(state["report"]), encoding="utf-8")
            server.HUNTS.pop(HUNT_ID)
            restored = (await client.get(f"/api/hunts/{HUNT_ID}")).json()
        assert seen[0]["require_live"] is True
        assert state["status"] == "error"
        assert state["report"]["live_api"]["status"] == "incomplete"
        assert downloaded.status_code == 200
        assert downloaded.json() == state["report"]
        assert "attachment" in downloaded.headers["content-disposition"]
        assert "ui-server-test-secret" not in downloaded.text
        assert invalid.status_code == 404
        assert restored["status"] == "error" and "401" in restored["error"]
    finally:
        server.HUNTS.pop(HUNT_ID, None)


@pytest.mark.asyncio
async def test_ui_live_request_is_strict_and_injected_evidence_is_never_live(server_url):
    requests = []

    async def api(route):
        path = urlsplit(route.request.url).path
        if path == "/api/config":
            data = {"meta_configured": True, "model": "muse-spark-1.3", "recorded_demos": ["composer"]}
        elif path == "/api/hunts":
            requests.append(route.request.post_data_json)
            data = {"id": HUNT_ID}
        else:
            latest = requests[-1]
            fixture = report(latest["url"], planner=latest["planner"], required=latest["require_live"])
            data = {"status": "done", "events": [], "error": None, "report": fixture}
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 375, "height": 812})
        await page.route("**/api/**", api)
        await page.goto(server_url, wait_until="domcontentloaded")
        await expect(page.locator("#model")).to_contain_text("live calls required")
        await expect(page.locator('[data-planner="meta"]')).to_have_text("Live Muse API")
        await page.locator("#run").click()
        await expect(page.locator("#apiEvidence")).to_be_visible()
        assert requests[0]["planner"] == "meta" and requests[0]["require_live"] is True
        await expect(page.locator("#apiEvidence")).to_have_attribute("data-state", "incomplete")
        await expect(page.locator("#apiSummary")).to_contain_text("Injected test responses are not live API evidence")
        await page.locator("#apiDetails summary").click()
        await expect(page.locator("#apiCalls")).to_contain_text("2026-10-27T12:00:00+00:00")
        await expect(page.locator("#apiCalls")).to_contain_text("faultline_plan")
        await expect(page.locator("#apiCalls")).to_contain_text("120 / 30")
        await expect(page.locator("#reportDownload")).to_have_attribute("href", f"/api/hunts/{HUNT_ID}/report")
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        # A claimed complete status cannot override missing model provenance or a fallback.
        for variant in ("missing_model", "different_model", "fallback"):
            fixture = report(server_url)
            fixture["live_api"]["calls"][0]["transport"] = "network"
            if variant == "missing_model":
                fixture["live_api"]["calls"][0]["reported_model"] = None
            elif variant == "different_model":
                fixture["live_api"]["calls"][0]["reported_model"] = "muse-wonder-1.0"
            else:
                fixture["planner"]["fallback_reason"] = "A model step failed"
            await page.evaluate("fixture => renderApiEvidence(fixture)", fixture)
            await expect(page.locator("#apiEvidence")).to_have_attribute("data-state", "incomplete")
        await page.locator('[data-demo="composer"]').click()
        await page.locator('[data-planner="recorded"]').click()
        await page.locator("#run").click()
        await expect(page.locator("#apiEvidence")).to_have_attribute("data-state", "not_requested")
        await expect(page.locator("#apiSummary")).to_contain_text("replays a recorded Muse plan")
        assert requests[-1]["planner"] == "recorded" and requests[-1]["require_live"] is False
        await page.locator('[data-planner="heuristic"]').click()
        await page.locator("#run").click()
        await expect(page.locator("#run")).to_be_enabled()
        assert requests[-1]["planner"] == "heuristic" and requests[-1]["require_live"] is False
        await browser.close()


@pytest.mark.asyncio
async def test_ui_missing_key_keeps_live_explicit_and_allows_rules(server_url):
    requests = []

    async def api(route):
        path = urlsplit(route.request.url).path
        if path == "/api/config":
            data = {"meta_configured": False, "recorded_demos": ["composer"]}
        elif path == "/api/hunts":
            requests.append(route.request.post_data_json)
            data = {"id": HUNT_ID}
        else:
            data = {"status": "done", "events": [], "error": None,
                    "report": report(server_url, planner="heuristic", required=False)}
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.route("**/api/**", api)
        await page.goto(server_url, wait_until="domcontentloaded")
        await expect(page.locator("#model")).to_contain_text("MODEL_API_KEY")
        await page.locator("#run").click()
        await expect(page.locator("#status")).to_contain_text("Keep the key on the server")
        assert requests == []
        assert await page.locator('input[type="password"]').count() == 0
        await page.locator('[data-planner="heuristic"]').click()
        await page.locator("#run").click()
        await expect(page.locator("#apiEvidence")).to_be_visible()
        assert requests[-1]["require_live"] is False
        await browser.close()


@pytest.mark.asyncio
async def test_ui_preserves_api_evidence_when_hunt_fails(server_url):
    async def api(route):
        path = urlsplit(route.request.url).path
        if path == "/api/config":
            data = {"meta_configured": True, "model": "muse-spark-1.3"}
        elif path == "/api/hunts":
            data = {"id": HUNT_ID}
        else:
            fixture = report(server_url)
            fixture.update(status="error", error="Meta endpoint returned HTTP 401")
            fixture["live_api"].update(status="incomplete", network_successes=0)
            fixture["live_api"]["calls"][0].update(transport="network", success=False, http_status=401, status="http_error")
            data = {"status": "error", "events": [], "error": fixture["error"], "report": fixture}
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.route("**/api/**", api)
        await page.goto(server_url, wait_until="domcontentloaded")
        await expect(page.locator("#model")).to_contain_text("live calls required")
        await page.locator("#run").click()
        await expect(page.locator("#status")).to_contain_text("hunt stopped")
        await expect(page.locator("#apiEvidence")).to_have_attribute("data-state", "incomplete")
        await expect(page.locator("#reportDownload")).to_be_visible()
        await page.locator("#apiDetails summary").click()
        await expect(page.locator("#apiCalls")).to_contain_text("401")
        await browser.close()
