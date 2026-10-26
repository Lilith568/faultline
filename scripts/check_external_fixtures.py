"""Sanity-check the pinned upstream fixtures separately from Faultline's planner.

These explicit Playwright checks establish that the downloaded upstream apps
load and function locally. They are not autonomous discoveries or Muse results.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlsplit
import uuid

from playwright.async_api import async_playwright


async def check(args) -> dict:
    result = {"scope": "manually_authored_fixture_smoke_checks", "started_at": datetime.now(timezone.utc).isoformat(),
              "meta_api_called": False, "checks": []}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            for app, url in (("todomvc", args.todomvc), ("2048", args.game)):
                parsed = urlsplit(url)
                if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
                    raise ValueError("Fixture checks only accept localhost or 127.0.0.1 URLs")
                context = await browser.new_context(service_workers="block")
                origin = (parsed.scheme, parsed.netloc)

                async def local_only(route):
                    target = urlsplit(route.request.url)
                    if (target.scheme, target.netloc) == origin:
                        await route.continue_()
                    else:
                        await route.abort()

                await context.route("**/*", local_only)
                page = await context.new_page()
                page.set_default_timeout(5000)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                entry = {"application": app, "url": url, "status": "running"}
                try:
                    response = await page.goto(url, wait_until="networkidle")
                    assert response is not None and response.status == 200
                    if app == "todomvc":
                        field = page.get_by_placeholder("What needs to be done?")
                        await field.fill("Faultline upstream smoke")
                        # This pinned ES5 implementation commits the field on its
                        # change event (blur), not a key handler for Enter.
                        await field.press("Tab")
                        await page.get_by_text("Faultline upstream smoke", exact=True).wait_for()
                        assert await page.locator(".todo-list li").count() == 1
                        await page.locator(".todo-list li .toggle").check()
                        await page.get_by_role("button", name="Clear completed").click()
                        assert await page.locator(".todo-list li").count() == 0
                        await field.fill("In-memory todo")
                        await field.press("Tab")
                        await page.get_by_text("In-memory todo", exact=True).wait_for()
                        await page.reload(wait_until="networkidle")
                        assert await page.locator(".todo-list li").count() == 0
                        entry["operations"] = ["create todo on blur", "complete todo", "clear completed",
                                               "reload resets documented in-memory storage"]
                    else:
                        await page.locator(".tile").first.wait_for()
                        assert await page.locator(".tile").count() == 2
                        for key in ("ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"):
                            await page.keyboard.press(key)
                            await page.wait_for_timeout(150)
                        state = await page.evaluate("JSON.parse(localStorage.getItem('gameState'))")
                        assert state and state.get("grid", {}).get("size") == 4
                        await page.locator(".restart-button").click()
                        await page.wait_for_timeout(200)
                        assert await page.locator(".tile").count() == 2
                        assert (await page.locator(".score-container").inner_text()).strip() == "0"
                        entry["operations"] = ["initial board", "keyboard moves", "state persisted", "new game resets board"]
                    assert not errors, errors
                    entry["status"] = "passed"
                except Exception as exc:
                    entry["status"] = "error"
                    entry["error"] = f"{type(exc).__name__}: {exc}"
                entry["page_errors"] = errors
                result["checks"].append(entry)
                await context.close()
        finally:
            await browser.close()
    result["finished_at"] = datetime.now(timezone.utc).isoformat()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--todomvc", default="http://127.0.0.1:8181/")
    parser.add_argument("--game", default="http://127.0.0.1:8182/")
    parser.add_argument("--output-root", default=str(Path(__file__).resolve().parents[1] / "eval" / "external"))
    args = parser.parse_args()
    result = asyncio.run(check(args))
    root = Path(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    path = root / f"smoke-{stamp}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(path)
    print(json.dumps(result, indent=2))
    return 0 if all(item["status"] == "passed" for item in result["checks"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
