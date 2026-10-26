"""Recorded Muse plans can be replayed from the UI on the bundled demo apps, without any model call."""
import asyncio

import httpx
import pytest

from faultline import server


def test_only_demo_apps_with_one_recording_are_offered():
    assert server.recorded_demos() == ["composer", "newsletter"]


@pytest.mark.parametrize("url,app", [
    ("http://127.0.0.1:8000/demo/composer.html?mode=buggy", "composer"),
    ("http://localhost:5173/demo/newsletter.html", "newsletter"),
    ("http://127.0.0.1:8000/demo/profile.html?mode=buggy", None),
    ("http://127.0.0.1:8000/demo/../eval/recorded/composer.html", None),
    ("http://127.0.0.1:8000/other/composer.html", None),
])
def test_recorded_plan_lookup_is_limited_to_bundled_demo_pages(url, app):
    plan = server.recorded_plan_for(url)
    if app is None:
        assert plan is None
    else:
        assert plan["provenance"]["file"].startswith(f"eval/recorded/{app}-")
        assert plan["plan"]["hypotheses"]


@pytest.mark.asyncio
async def test_recorded_planner_is_refused_without_a_recording():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://localhost:8000") as c:
        response = await c.post("/api/hunts", headers={"Origin": "http://localhost:8000"}, json={
            "url": "http://localhost:8000/demo/profile.html?mode=buggy", "planner": "recorded"})
        assert response.status_code == 400
        assert "composer" in response.json()["detail"]
        config = (await c.get("/api/config")).json()
        assert config["recorded_demos"] == ["composer", "newsletter"]


@pytest.mark.asyncio
async def test_recorded_plan_runs_through_the_ui_api_without_calling_a_model(server_url):
    async with httpx.AsyncClient(base_url=server_url, timeout=30) as c:
        started = await c.post("/api/hunts", json={"url": f"{server_url}/demo/composer.html?mode=buggy",
                                                   "planner": "recorded", "rounds": 2})
        assert started.status_code == 200, started.text
        hunt_id = started.json()["id"]
        for _ in range(240):
            state = (await c.get(f"/api/hunts/{hunt_id}")).json()
            if state["status"] != "running":
                break
            await asyncio.sleep(0.5)
    assert state["status"] == "done", state.get("error")
    report = state["report"]
    assert report["planner"]["used"] == "recorded"
    assert report["planner"]["recorded_from"]["file"].startswith("eval/recorded/composer-")
    assert report["meta_calls"] == [] and report["stats"]["meta_calls"] == 0
    assert len(report["rounds"]) == 1, "a recorded plan never triggers a model follow-up round"
    confirmed = [cx for cx in report["counterexamples"] if cx["confirmation"]["confirmed"]]
    assert {cx["fault_class"] for cx in confirmed} >= {"draft_loss", "double_submit"}
    assert all(cx["diagnosis"]["source"] == "template" for cx in confirmed)
