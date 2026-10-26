"""Local web app: Faultline UI, API and the bundled demo targets."""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .config import get_settings
from .export import spec_filename
from .hunt import Hunt, replay
from .patches import propose_patch

HERE = Path(__file__).resolve().parent
DEMO_DIR = HERE / "demo"
STATIC_DIR = HERE / "static"
DEMO_APPS = ("profile", "search", "checkout", "settings", "composer", "newsletter")
ID_RE = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{6}$")
CX_RE = re.compile(r"^cx[0-9]{1,3}$")

app = FastAPI(title="Faultline", version="0.2.0")
HUNTS: dict[str, dict] = {}


@app.middleware("http")
async def protect_local_api(request: Request, call_next):
    """A web page on another origin must not start local hunts or upload source."""
    if request.url.path.startswith("/api/"):
        # Origin equality alone is insufficient against DNS rebinding.
        try:
            host = urlsplit("//" + request.headers.get("host", "")).hostname or ""
            local_host = host.lower() == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local_host = host.lower() == "localhost"
        configured = {h.strip().lower() for h in os.getenv("FAULTLINE_UI_HOSTS", "").split(",") if h.strip()}
        if not local_host and host.lower() not in configured:
            return JSONResponse({"detail": "Unrecognized Faultline host."}, status_code=400)
    if request.url.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
        if (origin and origin.rstrip("/") != expected) or request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Use the Faultline page on the same origin."}, status_code=403)
        if request.url.path.endswith("/patch"):
            # Bound the actual streamed body, not only the optional Content-Length header.
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 300_000:
                    return JSONResponse({"detail": "Selected source files are too large."}, status_code=413)
            request._body = bytes(body)
    return await call_next(request)


# --------------------------------------------------------------------------- demo targets

def render_variant(html: str, mode: str) -> str:
    """Serve only the buggy or the fixed code path, like two real builds."""
    drop = "fixed" if mode == "buggy" else "buggy"
    html = re.sub(rf"^//<{drop}>\n.*?^//</{drop}>\n", "", html, flags=re.S | re.M)
    return re.sub(r"^//</?(buggy|fixed)>\n", "", html, flags=re.M)


@app.get("/demo/{name}.html", response_class=HTMLResponse)
def demo_page(name: str, mode: str = "buggy") -> str:
    if name not in DEMO_APPS or mode not in ("buggy", "fixed"):
        raise HTTPException(404)
    return render_variant((DEMO_DIR / f"{name}.html").read_text(encoding="utf-8"), mode)


@app.get("/demo/demo.css")
def demo_css() -> FileResponse:
    return FileResponse(DEMO_DIR / "demo.css", media_type="text/css")


PEOPLE = ["Ada Lovelace", "Alan Turing", "Annie Easley", "Barbara Liskov", "Carla Meninsky", "Catalina Vega",
          "Cathy Rodgers", "Dorothy Vaughan", "Edsger Dijkstra", "Frances Allen", "Grace Hopper", "Hedy Lamarr",
          "Ida Rhodes", "Jean Bartik", "Joan Clarke", "Karen Spärck Jones", "Katherine Johnson", "Kathleen Booth",
          "Lynn Conway", "Margaret Hamilton", "Mary Kenneth Keller", "Radia Perlman", "Ralph Baer", "Roberta Williams",
          "Sophie Wilson", "Susan Kare", "Tim Berners-Lee", "Toni Catanzaro", "Vint Cerf", "Wendy Hall",
          "Yukihiro Matsumoto", "Zelda Scott"]
STATE = {"orders": 1040, "notes": 17, "settings": {"email": "alerts@larkspur.example", "digest": "08:00"}}


@app.get("/demo-api/profile")
async def demo_profile():
    return {"name": "Grace Hopper", "bio": "Wrote the first compiler."}


@app.post("/demo-api/profile")
async def demo_profile_save(request: Request):
    return {"ok": True, **(await request.json())}


@app.get("/demo-api/people")
async def demo_people(q: str = ""):
    await asyncio.sleep(0.03)
    term = q.strip().lower()
    return {"q": q, "results": [p for p in PEOPLE if term and term in p.lower()][:8]}


@app.post("/demo-api/orders")
async def demo_orders():
    await asyncio.sleep(0.3)
    STATE["orders"] += 1
    return {"order_id": STATE["orders"]}


@app.get("/demo-api/settings")
async def demo_settings():
    return STATE["settings"]


@app.post("/demo-api/settings")
async def demo_settings_save(request: Request):
    await asyncio.sleep(0.1)
    return {"ok": True}


@app.post("/demo-api/notes")
async def demo_notes():
    await asyncio.sleep(0.3)
    STATE["notes"] += 1
    return {"id": STATE["notes"]}


@app.post("/demo-api/newsletter")
async def demo_newsletter():
    await asyncio.sleep(0.1)
    return {"ok": True}


# --------------------------------------------------------------------------- Faultline API

class HuntRequest(BaseModel):
    url: str
    goal: str = Field("", max_length=600)
    planner: str = Field("auto", pattern="^(auto|meta|heuristic)$")
    rounds: int = Field(2, ge=1, le=3)
    include_source: bool = False  # opt-in: send the page's inline scripts to Muse for the diagnosis


class ReplayRequest(BaseModel):
    hunt_id: str
    cx_id: str
    url: str


class SourceFile(BaseModel):
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=100_000)


class PatchRequest(BaseModel):
    files: list[SourceFile] = Field(min_length=1, max_length=5)
    consent: bool = Field(False, strict=True)


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/config")
def config() -> dict:
    s = get_settings()
    return {"meta_configured": s.meta_configured, "model": s.model, "reasoning_effort": s.reasoning_effort,
            "backend": getattr(s, "backend", "meta"),
            "demo_apps": DEMO_APPS}


@app.post("/api/hunts")
async def start_hunt(body: HuntRequest) -> dict:
    record: dict = {"status": "running", "events": [], "report": None, "error": None}

    def emit(kind: str, message: str, data: dict | None = None) -> None:
        record["events"].append({"kind": kind, "message": message, "data": data})

    try:
        hunt = Hunt(body.url, goal=body.goal, planner=body.planner, rounds=body.rounds,
                    include_source=body.include_source, emit=emit)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    HUNTS[hunt.id] = record

    async def runner() -> None:
        try:
            record["report"] = await hunt.run()
            record["status"] = "done"
        except Exception as exc:  # surface errors to the UI instead of failing silently
            record["status"] = "error"
            record["error"] = f"{type(exc).__name__}: {exc}"
            emit("error", record["error"])

    record["task"] = asyncio.create_task(runner())
    return {"id": hunt.id}


@app.get("/api/hunts/{hunt_id}")
def get_hunt(hunt_id: str, since: int = 0) -> JSONResponse:
    record = HUNTS.get(hunt_id)
    if record is None:
        report = _load_report(hunt_id)
        return JSONResponse({"status": "done", "events": [], "report": report, "error": None})
    return JSONResponse({"status": record["status"], "events": record["events"][since:],
                         "event_count": len(record["events"]),
                         "report": record["report"], "error": record["error"]})


def _load_report(hunt_id: str) -> dict:
    if not ID_RE.match(hunt_id):
        raise HTTPException(404)
    path = Path(get_settings().artifacts) / hunt_id / "report.json"
    if not path.exists():
        raise HTTPException(404)
    return json.loads(path.read_text(encoding="utf-8"))


def _cx(hunt_id: str, cx_id: str) -> dict:
    if not CX_RE.match(cx_id):
        raise HTTPException(404)
    record = HUNTS.get(hunt_id)
    report = record["report"] if record and record.get("report") else _load_report(hunt_id)
    for cx in report["counterexamples"]:
        if cx["id"] == cx_id:
            return cx
    raise HTTPException(404)


@app.get("/api/hunts/{hunt_id}/{cx_id}/spec")
def download_spec(hunt_id: str, cx_id: str) -> PlainTextResponse:
    cx = _cx(hunt_id, cx_id)
    text = Path(cx["spec_file"]).read_text(encoding="utf-8")
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="{spec_filename(cx)}"'})


@app.get("/api/hunts/{hunt_id}/{cx_id}/repro")
def download_repro(hunt_id: str, cx_id: str) -> FileResponse:
    cx = _cx(hunt_id, cx_id)
    return FileResponse(cx["repro_file"], media_type="application/json", filename=f"{cx_id}-repro.json")


@app.get("/api/hunts/{hunt_id}/{cx_id}/screenshot")
def screenshot(hunt_id: str, cx_id: str) -> FileResponse:
    cx = _cx(hunt_id, cx_id)
    if not cx.get("screenshot"):
        raise HTTPException(404)
    return FileResponse(cx["screenshot"], media_type="image/png")


@app.get("/api/hunts/{hunt_id}/{cx_id}/trace")
def trace(hunt_id: str, cx_id: str) -> FileResponse:
    cx = _cx(hunt_id, cx_id)
    if not cx.get("trace"):
        raise HTTPException(404)
    return FileResponse(cx["trace"], media_type="application/zip", filename=f"{cx_id}-trace.zip")


@app.post("/api/replay")
async def replay_cx(body: ReplayRequest) -> dict:
    cx = _cx(body.hunt_id, body.cx_id)
    repro = json.loads(Path(cx["repro_file"]).read_text(encoding="utf-8"))
    try:
        result = await replay(repro, body.url)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    failing = [r for r in result["invariants"] if r["status"] == "fail"]
    return {"status": result["status"], "error": result["error"], "failing": failing,
            "invariants": result["invariants"], "duration_ms": result["duration_ms"]}


@app.post("/api/hunts/{hunt_id}/{cx_id}/patch")
async def suggest_patch(hunt_id: str, cx_id: str, body: PatchRequest) -> dict:
    """Return a review-only proposal. Source and diffs are never written or executed."""
    cx = _cx(hunt_id, cx_id)
    return await propose_patch(get_settings(), cx, [f.model_dump() for f in body.files], body.consent)
