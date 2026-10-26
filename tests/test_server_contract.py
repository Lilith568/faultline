"""Local API consent boundaries and bounded source submission."""
import httpx
import pytest

from faultline import server


@pytest.mark.asyncio
async def test_matching_attacker_host_and_origin_are_rejected():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://attacker.example:8000") as c:
        response = await c.get("/api/config", headers={"Origin": "http://attacker.example:8000"})
        assert response.status_code == 400
        response = await c.post("/api/hunts", headers={"Origin": "http://attacker.example:8000"}, json={})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_cross_origin_cannot_start_a_hunt():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as c:
        response = await c.post("/api/hunts", headers={"Origin": "https://other.example"},
                                json={"url": "http://localhost:8000/demo/search.html"})
        assert response.status_code == 403
        response = await c.post("/api/hunts", headers={"Sec-Fetch-Site": "cross-site"}, json={})
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_patch_endpoint_keeps_consent_and_source_explicit(monkeypatch):
    seen = []
    monkeypatch.setattr(server, "_cx", lambda h, c: {"id": c})

    async def proposal(settings, finding, files, consent):
        seen.append((finding, files, consent))
        return {"status": "rejected", "diff": "", "reason": "Not enough evidence"}

    monkeypatch.setattr(server, "propose_patch", proposal)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as c:
        response = await c.post("/api/hunts/h/cx1/patch", headers={"Origin": "http://localhost:8000"},
                                json={"files": [{"path": "src/view.js", "content": "const x = 1;"}]})
        assert response.status_code == 200
        assert seen[0][2] is False
        assert seen[0][1] == [{"path": "src/view.js", "content": "const x = 1;"}]
        assert response.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_streamed_patch_body_is_bounded():
    async def chunks():
        for _ in range(4):
            yield b"x" * 100_000

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as c:
        response = await c.post("/api/hunts/h/cx1/patch", content=chunks(),
                                headers={"Content-Type": "application/json"})
        assert response.status_code == 413


@pytest.mark.asyncio
async def test_source_request_rejects_string_consent():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as c:
        response = await c.post("/api/hunts/h/cx1/patch", json={
            "files": [{"path": "a.js", "content": "x"}], "consent": "yes"})
        assert response.status_code == 422
