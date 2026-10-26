"""Page discovery: build an addressable inventory of a local web app.

Discovery never guesses selectors. Every element gets a ref (e1, e2, ...) and a
locator spec (test id, role + accessible name, label, placeholder or text) that
was checked to match exactly one element. A short, side-effect-aware
exploration clicks "opener" controls and types into inputs so the planner learns
which controls reveal which fields and which API endpoints they trigger.
"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Browser, Page

SCAN_JS = r"""
() => {
  const SEL = [
    'a[href]', 'button', 'input', 'textarea', 'select', '[role=button]', '[role=link]',
    '[role=textbox]', '[role=searchbox]', '[role=combobox]', '[role=checkbox]', '[role=switch]',
    '[role=tab]', '[role=menuitem]', '[contenteditable="true"]', '[data-testid]', '[role=dialog]',
    'dialog', '[role=alert]', '[role=status]', '[role=log]', '[aria-live]', '[role=region][aria-label]',
    '[role=list][aria-label]', 'output'
  ].join(',');
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const visible = el => {
    if (!el.isConnected || el.closest('[hidden]')) return false;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  };
  const labelText = el => {
    const aria = el.getAttribute('aria-label');
    if (aria) return clean(aria);
    const by = el.getAttribute('aria-labelledby');
    if (by) return clean(by.split(/\s+/).map(id => (document.getElementById(id) || {}).textContent || '').join(' '));
    if (el.id) {
      const l = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
      if (l) return clean(l.textContent);
    }
    const wrap = el.closest('label');
    if (wrap) return clean(wrap.textContent);
    return '';
  };
  const roleOf = el => {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit.split(/\s+/)[0];
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || 'text').toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'a') return 'link';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'dialog') return 'dialog';
    if (tag === 'output') return 'status';
    if (tag === 'input') {
      if (['button', 'submit', 'reset'].includes(type)) return 'button';
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'search') return 'searchbox';
      if (['hidden', 'file', 'range', 'color', 'image'].includes(type)) return '';
      return 'textbox';
    }
    if (el.isContentEditable) return 'textbox';
    if (el.hasAttribute('aria-live')) return 'status';
    return '';
  };
  const groupOf = el => {
    const g = el.closest('form, dialog, [role=dialog], [role=tabpanel], section[aria-label], [data-testid]:not(input):not(button):not(textarea)');
    if (!g || g === el) return '';
    return g.getAttribute('data-testid') || g.getAttribute('aria-label') || g.id || g.tagName.toLowerCase();
  };
  const out = [];
  for (const el of Array.from(document.querySelectorAll(SEL))) {
    const tag = el.tagName.toLowerCase();
    const type = (el.getAttribute('type') || '').toLowerCase();
    const role = roleOf(el);
    const textLike = (tag === 'input' && !['button','submit','reset','checkbox','radio','hidden','file','range','color','image'].includes(type))
      || tag === 'textarea' || el.isContentEditable;
    const editable = textLike && !el.disabled && !el.readOnly;
    const container = ['dialog','alert','status','log','region','list','tabpanel'].includes(role) || tag === 'output';
    let name = labelText(el);
    if (!name && textLike) name = clean(el.getAttribute('placeholder') || el.getAttribute('title'));
    if (!name && !container) name = clean(el.innerText || el.value || el.getAttribute('title')).slice(0, 60);
    out.push({
      tag, type, role, name: name.slice(0, 80),
      testid: el.getAttribute('data-testid') || '',
      placeholder: el.getAttribute('placeholder') || '',
      editable, password: type === 'password',
      container,
      visible: visible(el),
      in_dialog: !!el.closest('dialog, [role=dialog]'),
      group: groupOf(el),
      disabled: !!el.disabled,
      haspopup: !!(el.getAttribute('aria-haspopup') || el.getAttribute('aria-controls') || el.hasAttribute('aria-expanded')),
      text: container ? clean(el.innerText).slice(0, 160) : '',
    });
  }
  return out;
}
"""

ACTIVE_JS = r"""
() => {
  const visibleDialogs = Array.from(document.querySelectorAll('dialog[open], [role=dialog], [aria-modal="true"]'))
    .filter(d => !d.closest('[hidden]') && getComputedStyle(d).display !== 'none' && getComputedStyle(d).visibility !== 'hidden');
  const a = document.activeElement;
  return {
    dialogs: new Set(visibleDialogs).size,
    active: a && a !== document.body ? {
      tag: a.tagName.toLowerCase(), testid: a.getAttribute('data-testid') || '',
      id: a.id || '', name: (a.getAttribute('aria-label') || a.innerText || a.value || '').trim().slice(0, 60)
    } : null
  };
}
"""

DESTRUCTIVE = re.compile(
    r"delete|remove|destroy|pay|purchase|buy|order|checkout|submit|send|publish|post\b|save|sign ?out|"
    r"log ?out|logout|confirm|book|transfer|subscribe|deactivate|reset|clear|discard|archive|approve",
    re.I,
)
OPENER_HINT = re.compile(r"edit|open|add|new|settings|menu|more|details|compose|write|preview|show|expand|filter|profile",
                         re.I)


def locator_for(page: Page, spec: dict):
    """Turn a locator spec into a Playwright locator (also used by exported tests)."""
    by, value = spec["by"], spec["value"]
    if by == "testid":
        return page.get_by_test_id(value)
    if by == "role":
        return page.get_by_role(spec["role"], name=value, exact=True, include_hidden=True)
    if by == "label":
        return page.get_by_label(value, exact=True)
    if by == "placeholder":
        return page.get_by_placeholder(value, exact=True)
    if by == "text":
        return page.get_by_text(value, exact=True)
    raise ValueError(f"unknown locator strategy {by!r}")


def _candidate_specs(item: dict) -> list[dict]:
    specs = []
    if item["testid"]:
        specs.append({"by": "testid", "value": item["testid"]})
    if item["role"] and item["name"]:
        specs.append({"by": "role", "role": item["role"], "value": item["name"]})
    if item["editable"] and item["name"]:
        specs.append({"by": "label", "value": item["name"]})
    if item["placeholder"]:
        specs.append({"by": "placeholder", "value": item["placeholder"]})
    if not item["editable"] and not item["container"] and item["name"]:
        specs.append({"by": "text", "value": item["name"]})
    return specs


def spec_key(spec: dict) -> str:
    return f"{spec['by']}|{spec.get('role', '')}|{spec['value']}"


async def _unique_spec(page: Page, item: dict) -> dict | None:
    for spec in _candidate_specs(item):
        try:
            if await locator_for(page, spec).count() == 1:
                return spec
        except Exception:
            continue
    return None


async def scan(page: Page) -> list[dict]:
    """Scan the current page state and return addressable elements (without refs)."""
    raw = await page.evaluate(SCAN_JS)
    found: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not item["role"] and not item["testid"]:
            continue
        if item["disabled"] and not item["editable"]:
            pass  # disabled controls are still useful context
        spec = await _unique_spec(page, item)
        if not spec:
            continue
        key = spec_key(spec)
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "role": item["role"] or ("textbox" if item["editable"] else ""),
            "name": item["name"],
            "testid": item["testid"],
            "tag": item["tag"],
            "input_type": item["type"],
            "editable": bool(item["editable"]) and not item["password"],
            "password": bool(item["password"]),
            "container": bool(item["container"]),
            "visible": bool(item["visible"]),
            "in_dialog": bool(item["in_dialog"]),
            "group": item["group"],
            "haspopup": bool(item["haspopup"]),
            "text": item["text"],
            "locator": spec,
        })
    return found


def _same_origin(url: str, origin: str) -> bool:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" == origin


def origin_of(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


class _RequestLog:
    def __init__(self, origin: str):
        self.origin = origin
        self.items: list[str] = []

    def __call__(self, request) -> None:
        if request.resource_type in ("fetch", "xhr") and _same_origin(request.url, self.origin):
            self.items.append(f"{request.method.upper()} {urlparse(request.url).path}")

    def since(self, index: int) -> list[str]:
        return list(dict.fromkeys(self.items[index:]))


async def _open(browser: Browser, url: str):
    context = await browser.new_context(viewport={"width": 1280, "height": 800})
    page = await context.new_page()
    log = _RequestLog(origin_of(url))
    context.on("request", log)
    await page.goto(url, wait_until="load")
    await page.wait_for_timeout(350)
    return context, page, log


INLINE_SOURCE_JS = r"""
() => Array.from(document.scripts).filter(s => !s.src).map(s => s.textContent).join('\n/* ---- */\n')
"""


async def discover(browser: Browser, url: str, *, max_openers: int = 6, max_inputs: int = 4,
                   settle_ms: int = 700) -> dict[str, Any]:
    context, page, log = await _open(browser, url)
    try:
        title = await page.title()
        base = await scan(page)
        load_endpoints = log.since(0)
        try:
            aria = await page.locator("body").aria_snapshot()
        except Exception:
            aria = ""
        source = await page.evaluate(INLINE_SOURCE_JS)
    finally:
        await context.close()

    elements: list[dict] = []
    by_key: dict[str, dict] = {}

    def add(item: dict, revealed_by: str | None = None) -> dict:
        key = spec_key(item["locator"])
        if key in by_key:
            return by_key[key]
        item = dict(item, ref=f"e{len(elements) + 1}", revealed_by=revealed_by,
                    triggers=[], updates=[])
        elements.append(item)
        by_key[key] = item
        return item

    for item in base:
        add(item)

    endpoints = list(dict.fromkeys(load_endpoints))
    notes: list[str] = []

    openers = [e for e in elements if e["visible"] and e["role"] in ("button", "tab", "menuitem")
               and not DESTRUCTIVE.search(e["name"] or "")
               and (e["haspopup"] or e["role"] == "tab" or OPENER_HINT.search(e["name"] or e["testid"] or ""))]
    for opener in openers[:max_openers]:
        context, page, log = await _open(browser, url)
        try:
            mark = len(log.items)
            before = {spec_key(s["locator"]): s["visible"] for s in await scan(page)}
            await locator_for(page, opener["locator"]).click(timeout=3000)
            await page.wait_for_timeout(settle_ms)
            after = await scan(page)
            revealed = []
            for item in after:
                key = spec_key(item["locator"])
                if item["visible"] and not before.get(key, False):
                    element = add(item, revealed_by=opener["ref"])
                    if element["revealed_by"] is None and not element["visible"]:
                        element["revealed_by"] = opener["ref"]
                    revealed.append(element["ref"])
            triggered = log.since(mark)
            opener["triggers"] = triggered
            endpoints.extend(triggered)
            if revealed or triggered:
                notes.append(f"Clicking {opener['ref']} reveals {revealed or 'nothing new'}"
                             f" and triggers {triggered or 'no API call'}")
        except Exception as exc:  # exploration is best effort
            notes.append(f"Clicking {opener['ref']} failed during exploration: {type(exc).__name__}")
        finally:
            await context.close()

    inputs = [e for e in elements if e["visible"] and e["editable"] and not e["in_dialog"]]
    for field in inputs[:max_inputs]:
        context, page, log = await _open(browser, url)
        try:
            mark = len(log.items)
            texts_before = {spec_key(s["locator"]): s["text"] for s in await scan(page) if s["container"]}
            await locator_for(page, field["locator"]).press_sequentially("ab", delay=60, timeout=3000)
            await page.wait_for_timeout(settle_ms)
            texts_after = {spec_key(s["locator"]): s["text"] for s in await scan(page) if s["container"]}
            updated = [by_key[k]["ref"] for k, v in texts_after.items()
                       if k in by_key and texts_before.get(k) != v]
            field["triggers"] = log.since(mark)
            field["updates"] = updated
            endpoints.extend(field["triggers"])
            if field["triggers"] or updated:
                notes.append(f"Typing into {field['ref']} triggers {field['triggers'] or 'no API call'}"
                             f" and updates {updated or 'no live region'}")
        except Exception as exc:
            notes.append(f"Typing into {field['ref']} failed during exploration: {type(exc).__name__}")
        finally:
            await context.close()

    return {
        "url": url,
        "title": title,
        "elements": elements,
        "endpoints": list(dict.fromkeys(endpoints)),
        "load_endpoints": load_endpoints,
        "notes": notes,
        "aria": aria[:4000],
        "source": source[:16000],
    }


async def probe(page: Page) -> dict:
    return await page.evaluate(ACTIVE_JS)


def model_view(inventory: dict) -> dict:
    """Compact, model-facing view of the inventory (no locator internals)."""
    rows = []
    for e in inventory["elements"]:
        row = {"ref": e["ref"], "role": e["role"], "name": e["name"]}
        for key in ("testid", "group", "text"):
            if e.get(key):
                row[key] = e[key]
        for key in ("editable", "password", "in_dialog", "container"):
            if e.get(key):
                row[key] = True
        if not e["visible"]:
            row["initially_hidden"] = True
        if e.get("revealed_by"):
            row["revealed_by"] = e["revealed_by"]
        if e.get("triggers"):
            row["triggers"] = e["triggers"]
        if e.get("updates"):
            row["updates"] = e["updates"]
        rows.append(row)
    return {"title": inventory.get("title", ""), "elements": rows,
            "endpoints": inventory["endpoints"], "exploration_notes": inventory["notes"]}


async def run_discovery(url: str, **kwargs) -> dict:  # convenience for scripts
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        try:
            return await discover(browser, url, **kwargs)
        finally:
            await browser.close()


if __name__ == "__main__":  # pragma: no cover
    import json
    import sys
    print(json.dumps(asyncio.run(run_discovery(sys.argv[1])), indent=2))
