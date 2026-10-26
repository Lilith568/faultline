"""Deterministic Playwright executor with network perturbations."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Browser

from .discover import ACTIVE_JS, locator_for, origin_of
from .invariants import evaluate, overall_status, signature
from .vocab import endpoint_matches

INJECTED_BODY = json.dumps({"error": "injected by Faultline"})


async def _read_state(page, exp: dict, elements: dict) -> dict:
    state = await page.evaluate(ACTIVE_JS)
    observed = {"dialogs": state["dialogs"], "active": state["active"], "values": {}, "texts": {}, "focus": {}}
    for inv in exp["invariants"]:
        ref = inv.get("ref")
        try:
            if inv["kind"] == "value_equals":
                loc = locator_for(page, elements[ref]["locator"])
                if await loc.count() == 1:
                    tag = elements[ref].get("tag")
                    if tag in ("input", "textarea", "select"):
                        observed["values"][ref] = await loc.input_value(timeout=1000)
                    else:
                        observed["values"][ref] = (await loc.inner_text(timeout=1000)).strip()
            elif inv["kind"] == "text_contains":
                if ref == "page":
                    observed["texts"][ref] = await page.locator("body").inner_text(timeout=1000)
                else:
                    loc = locator_for(page, elements[ref]["locator"])
                    if await loc.count() == 1:
                        observed["texts"][ref] = await loc.inner_text(timeout=1000)
            elif inv["kind"] == "focus_returns":
                loc = locator_for(page, elements[ref]["locator"])
                observed["focus"][ref] = (await loc.count() == 1
                                          and await loc.evaluate("el => el === document.activeElement"))
        except Exception:
            continue
    return observed


async def run_experiment(browser: Browser, url: str, exp: dict, inventory: dict, *,
                         screenshot: Path | None = None, trace: Path | None = None,
                         action_timeout: int = 3500, settle_ms: int = 450, pace_ms: int = 120) -> dict:
    """Run one experiment in a fresh browser context and verify its invariants."""
    elements = {e["ref"]: e for e in inventory["elements"]}
    origin = origin_of(url)
    perturbations = exp.get("perturbations", [])
    counters = [0] * len(perturbations)
    network: list[dict] = []
    page_errors: list[str] = []
    started = time.monotonic()

    context = await browser.new_context(viewport={"width": 1280, "height": 800})
    if trace:
        await context.tracing.start(screenshots=True, snapshots=True)

    def same_origin(request_url: str) -> bool:
        return origin_of(request_url) == origin

    async def route_handler(route):
        request = route.request
        try:
            if request.resource_type in ("fetch", "xhr") and same_origin(request.url):
                method, path = request.method.upper(), urlparse(request.url).path
                for index, p in enumerate(perturbations):
                    if not endpoint_matches(p["endpoint"], method, path):
                        continue
                    counters[index] += 1
                    if p["nth"] not in (0, counters[index]):
                        continue
                    if p["kind"] == "delay":
                        await asyncio.sleep(p["ms"] / 1000)
                    else:
                        await route.fulfill(status=p["status"], content_type="application/json",
                                            body=INJECTED_BODY)
                        return
            await route.continue_()
        except Exception:
            pass  # the context may close while a delayed request is still held

    def on_request(request) -> None:
        if request.resource_type in ("fetch", "xhr") and same_origin(request.url):
            network.append({"method": request.method.upper(), "path": urlparse(request.url).path,
                            "t_ms": int((time.monotonic() - started) * 1000)})

    if perturbations:
        await context.route("**/*", route_handler)
    context.on("request", on_request)
    page = await context.new_page()
    page.on("pageerror", lambda exc: page_errors.append(str(exc)[:300]))

    probes: list[dict] = []
    error = None
    error_step = None
    results: list[dict] = []
    try:
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(250)
        probes.append(await page.evaluate(ACTIVE_JS))
        for index, step in enumerate(exp["steps"]):
            action = step["action"]
            try:
                if action in ("click", "dblclick", "fill", "type"):
                    loc = locator_for(page, elements[step["ref"]]["locator"])
                    if action == "click":
                        await loc.click(timeout=action_timeout)
                    elif action == "dblclick":
                        await loc.dblclick(timeout=action_timeout)
                    elif action == "fill":
                        await loc.fill(step["value"], timeout=action_timeout)
                    else:
                        await loc.press_sequentially(step["value"], delay=120, timeout=action_timeout + 3000)
                elif action == "press":
                    await page.keyboard.press(step["key"])
                elif action == "wait":
                    await page.wait_for_timeout(step["ms"])
                elif action == "reload":
                    await page.reload(wait_until="load")
                if action != "wait" and pace_ms:
                    await page.wait_for_timeout(pace_ms)  # human-like pacing; races are induced on purpose
            except Exception as exc:
                error = f"step {index + 1} ({action}) could not run: {str(exc).splitlines()[0][:200]}"
                error_step = index
                break
            probes.append(await page.evaluate(ACTIVE_JS))
        if error is None:
            await page.wait_for_timeout(settle_ms)
            observed = await _read_state(page, exp, elements)
            results = evaluate(exp, observed, probes, network, page_errors)
        if screenshot:
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(screenshot))
    except Exception as exc:  # navigation failures and similar
        error = error or f"run failed: {str(exc).splitlines()[0][:200]}"
    finally:
        if trace:
            try:
                trace.parent.mkdir(parents=True, exist_ok=True)
                await context.tracing.stop(path=str(trace))
            except Exception:
                trace = None
        await context.close()

    status = overall_status(results, error)
    return {
        "status": status,
        "invariants": results,
        "signature": signature(results),
        "error": error,
        "error_step": error_step,
        "network": network,
        "page_errors": page_errors,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "screenshot": str(screenshot) if screenshot and screenshot.exists() else None,
        "trace": str(trace) if trace and Path(trace).exists() else None,
    }
