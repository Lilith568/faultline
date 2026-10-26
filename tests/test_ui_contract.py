"""UI behavior in Chromium with deterministic API fixtures; no model calls."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright, expect


HUNT_ID = "20261027-100000-abcdef"


def example_report(url: str, *, findings: bool = True) -> dict:
    """Small UI fixture, deliberately separate from evaluation measurements."""
    hypotheses = [{"id": "example", "claim": "A repeated action sends two requests", "result": {"status": "failed"}}] if findings else []
    return {
        "id": HUNT_ID, "url": url, "planner": {"used": "heuristic", "model": None, "fallback_reason": None},
        "stats": {"browser_runs": 6 if findings else 0, "meta_calls": 0, "duration_s": 1.2},
        "rounds": [{"round": 1, "hypotheses": hypotheses}], "unconfirmed": [],
        "counterexamples": [{
            "id": "cx1", "title": "A repeated action sends two requests", "hypothesis_ids": ["example"],
            "confirmation": {"failures": 3, "runs": 3}, "original_steps": 2, "fault_class": "double_submit",
            "experiment": {"steps": [{"action": "dblclick"}]},
            "text": {"steps": ["Double-click Submit"], "perturbations": []},
            "failure": {"invariant": "At most one request", "expected": "At most 1", "actual": "2 requests"},
            "attribution": "Reproduces without a network fault.", "screenshot": None, "trace": None,
            "diagnosis": {"source": "template", "root_cause": "The button remains enabled.",
                          "user_impact": "The action repeats.", "fix": "Disable it while pending."},
        }] if findings else [],
    }


@pytest.mark.asyncio
async def test_mobile_phases_test_preview_retest_and_source_consent(server_url):
    state = {"finish": False, "polls": 0, "retest": "passed", "patches": [], "hunts": []}
    target = f"{server_url}/demo/checkout.html?mode=buggy"
    exported = "import { test } from '@playwright/test';\n// Exact exported test fixture.\n"

    async def api(route):
        request = route.request
        path = urlsplit(request.url).path
        if path == "/api/config":
            data = {"meta_configured": True, "model": "muse-spark-1.3", "reasoning_effort": "medium"}
        elif path == "/api/hunts" and request.method == "POST":
            state["hunts"].append(request.post_data_json)
            data = {"id": HUNT_ID}
        elif path.endswith("/spec"):
            await route.fulfill(status=200, content_type="text/plain", body=exported)
            return
        elif path == "/api/replay":
            data = {"status": state["retest"], "error": "The local server stopped." if state["retest"] == "error" else None,
                    "failing": [], "invariants": [], "duration_ms": 40}
        elif path.endswith("/patch"):
            state["patches"].append(request.post_data_json)
            data = {"status": "proposed", "model": "muse-spark-1.3",
                    "diff": "--- a/app.js\n+++ b/app.js\n@@ -1 +1 @@\n-const ready = false;\n+const ready = true;\n"}
        else:
            events = [] if state["polls"] else [
                {"kind": "phase", "message": "Exploring the page", "data": {"phase": "explore"}},
                {"kind": "phase", "message": "Follow-up is not needed", "data": {"phase": "followup", "phase_status": "skipped"}},
                {"kind": "phase", "message": "Checking the experiment", "data": {"phase": "verify"}},
            ]
            state["polls"] += 1
            data = {"status": "done" if state["finish"] else "running", "events": events,
                    "report": example_report(target) if state["finish"] else None, "error": None}
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 375, "height": 812}, reduced_motion="reduce")
        await page.route("**/api/**", api)
        await page.goto(server_url, wait_until="domcontentloaded")
        await page.locator('[data-demo="checkout"]').click()
        await page.locator("#run").click()
        await expect(page.locator('[data-phase="verify"]')).to_have_attribute("aria-current", "step")
        await expect(page.locator('[data-phase="followup"]')).to_have_attribute("data-state", "skipped")
        await expect(page.locator("#url")).to_be_disabled()
        assert await page.locator("#seis animate").count() == 0
        assert state["hunts"][0]["url"] == target
        state["finish"] = True
        await expect(page.locator(".sheet")).to_be_visible()
        await expect(page.locator(".hyps .verdict")).to_have_text("Verified failure")
        await expect(page.locator('[data-phase="verify"]')).to_have_attribute("data-state", "done")
        await expect(page.locator("#url")).to_be_enabled()
        await page.locator("[data-spec] summary").click()
        await expect(page.locator("[data-spec] code")).to_have_text(exported)
        await page.locator("[data-retest]").click()
        await expect(page.locator(".result strong")).to_have_text("Check passed on this build")
        await expect(page.locator(".tested-url")).to_contain_text("mode=fixed")
        state["retest"] = "error"
        await page.locator("[data-retest]").click()
        await expect(page.locator(".result strong")).to_have_text("Re-test was inconclusive")
        assert "ok" not in (await page.locator(".result").get_attribute("class")).split()
        await page.locator("[data-patch-panel] summary").click()
        await page.locator("[data-patch-files]").set_input_files({
            "name": "app.js", "mimeType": "text/javascript", "buffer": b"const ready = false;\n"})
        await expect(page.locator("[data-source-index]")).to_have_value("app.js")
        await expect(page.locator("[data-patch]")).to_be_disabled()
        assert state["patches"] == []
        await page.locator("[data-patch-consent]").check()
        await expect(page.locator("[data-patch]")).to_be_enabled()
        await page.locator("[data-patch]").click()
        await expect(page.locator(".patch-output")).to_be_visible()
        assert state["patches"] == [{"files": [{"path": "app.js", "content": "const ready = false;\n"}], "consent": True}]
        await expect(page.locator("[data-patch-consent]")).not_to_be_checked()
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await browser.close()


@pytest.mark.asyncio
async def test_zero_experiments_are_not_presented_as_a_pass(server_url):
    async def api(route):
        path = urlsplit(route.request.url).path
        if path == "/api/config":
            data = {"meta_configured": False}
        elif path == "/api/hunts":
            data = {"id": HUNT_ID}
        else:
            data = {"status": "done", "events": [], "error": None,
                    "report": example_report(server_url + "/demo/profile.html?mode=buggy", findings=False)}
        await route.fulfill(status=200, content_type="application/json", body=json.dumps(data))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 375, "height": 812})
        await page.route("**/api/**", api)
        await page.goto(server_url, wait_until="domcontentloaded")
        await page.keyboard.press("Tab")
        assert await page.locator(".skip").evaluate("element => element === document.activeElement")
        assert await page.locator(".skip").evaluate("element => getComputedStyle(element).outlineWidth") == "3px"
        await page.locator("#run").click()
        await expect(page.locator("#findingCount")).to_have_text("No coverage")
        await expect(page.locator("#cxs h3")).to_have_text("No experiments were available.")
        await expect(page.locator("#status")).to_contain_text("No applicable checks completed")
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        await browser.close()
