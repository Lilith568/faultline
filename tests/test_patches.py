"""Proposals are consent-gated data, with source-grounded diff validation."""
import copy
import difflib
import json
from pathlib import Path

import httpx
import pytest

from faultline.config import Settings
from faultline.patches import PatchError, propose_patch, validate_diff, validate_sources

SOURCE = "let revision = 0;\nfunction save(value) {\n  render(value);\n}\n"
FIXED = "let revision = 0;\nfunction save(value) {\n  revision += 1;\n  render(value);\n}\n"
DIFF = "".join(difflib.unified_diff(SOURCE.splitlines(True), FIXED.splitlines(True),
                                    fromfile="a/src/editor.js", tofile="b/src/editor.js"))
CX = {"title": "A late response loses an edit", "confirmation": {"confirmed": True, "runs": 3, "failures": 3},
      "text": {"steps": ["Enter a draft"], "perturbations": ["Delay GET /profile"]},
      "failure": {"expected": "draft", "actual": "old text"}}


def settings(tmp_path):
    return Settings("test-key", "https://api.meta.test/v1", "muse-spark-1.3", None, False, tmp_path)


def fake_patch(payload, calls):
    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"model": "muse-spark-1.3", "usage": {},
                                         "choices": [{"message": {"content": json.dumps(payload)}}]})
    return httpx.MockTransport(handle)


@pytest.mark.parametrize("path", ["../editor.js", "/tmp/editor.js", "a/../../editor.js", "a\\editor.js",
                                 "C:/editor.js", ".env", ".env.js", ".git/config.js", "secret.pem",
                                 "src//editor.js", "src/./editor.js", "node_modules/x.js"])
def test_source_path_boundary(path):
    with pytest.raises(PatchError):
        validate_sources([{"path": path, "content": "code"}], True)


@pytest.mark.parametrize("source", ["const api_key = 'abcdef0123456789';", "-----BEGIN PRIVATE KEY-----",
                                   "const token = 'ghp_abcdefghijklmnopqrstuvw';", "bad\x00text"])
def test_sensitive_source_is_refused(source):
    with pytest.raises(PatchError):
        validate_sources([{"path": "app.js", "content": source}], True)


def test_source_limits_and_case_collision():
    with pytest.raises(PatchError):
        validate_sources([{"path": "app.js", "content": "x" * 64001}], True)
    with pytest.raises(PatchError):
        validate_sources([{"path": "App.js", "content": "a"}, {"path": "app.js", "content": "b"}], True)


def test_diff_hunks_match_source_and_never_touch_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    sources = {"src/editor.js": SOURCE}
    before = copy.deepcopy(sources)
    assert validate_diff(DIFF, sources) == ["src/editor.js"]
    assert sources == before
    assert list(tmp_path.iterdir()) == []
    for bad in (
        DIFF.replace("revision = 0", "revision = 99"),
        DIFF.replace("@@ -1,4 +1,5 @@", "@@ -1,3 +1,5 @@"),
        DIFF.replace("b/src/editor.js", "b/src/another.js"),
        DIFF.replace("src/editor.js", "src/unselected.js"),
        DIFF + "\nRun this shell command\n",
        DIFF + DIFF,
        "--- /dev/null\n+++ b/src/new.js\n@@ -0,0 +1 @@\n+new\n",
    ):
        with pytest.raises(PatchError):
            validate_diff(bad, sources)


def test_multiple_hunks_and_files():
    source = "".join(f"line {i}\n" for i in range(20))
    revised = source.replace("line 1\n", "revised 1\n").replace("line 18\n", "revised 18\n")
    diff = "".join(difflib.unified_diff(source.splitlines(True), revised.splitlines(True),
                                       fromfile="a/app.py", tofile="b/app.py", n=1))
    assert validate_diff(diff + DIFF, {"app.py": source, "src/editor.js": SOURCE}) == ["app.py", "src/editor.js"]
    with pytest.raises(PatchError):
        validate_diff(diff.replace("+18,3", "+19,3"), {"app.py": source})


def test_insert_at_start_and_delete_last_line():
    for old, new in (("", "x\n"), ("a\nb\n", "a\n"), ("b\n", "a\nb\n")):
        diff = "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                           fromfile="a/app.js", tofile="b/app.js"))
        assert validate_diff(diff, {"app.js": old}) == ["app.js"]


def test_untrusted_huge_hunk_coordinates_are_a_patch_rejection():
    diff = "--- a/app.js\n+++ b/app.js\n@@ -" + "9" * 5000 + ",1 +1,1 @@\n-x\n+y\n"
    with pytest.raises(PatchError, match="Malformed unified diff hunk"):
        validate_diff(diff, {"app.js": "x\n"})


@pytest.mark.asyncio
async def test_no_network_without_consent_or_with_unconfirmed_failure(tmp_path):
    calls = []
    transport = fake_patch({}, calls)
    files = [{"path": "src/editor.js", "content": SOURCE}]
    for cx, consent in ((CX, False), ({**CX, "confirmation": {"confirmed": False}}, True),
                        ({**CX, "confirmation": {"confirmed": True, "runs": 1, "failures": 1}}, True)):
        result = await propose_patch(settings(tmp_path), cx, files, consent, transport=transport)
        assert result["status"] == "rejected" and result["diff"] == ""
    assert calls == []


@pytest.mark.asyncio
async def test_proposal_includes_only_selected_sources_and_is_not_applied(tmp_path):
    original = tmp_path / "untouched.js"
    original.write_text("do not read this", encoding="utf-8")
    calls = []
    result = await propose_patch(settings(tmp_path), CX, [{"path": "src/editor.js", "content": SOURCE}], True,
                                 transport=fake_patch({"diff": DIFF, "can_patch": True,
                                                       "explanation": "Review the revision guard."}, calls))
    assert result["status"] == "proposed" and result["diff"] == DIFF
    assert result["review_only"] and result["verified_fix"] is False
    assert result["files"] == ["src/editor.js"]
    assert len(result["source_sha256"]["src/editor.js"]) == 64
    sent = json.loads(calls[0]["messages"][1]["content"])
    assert sent["selected_source_files"] == [{"path": "src/editor.js", "content": SOURCE}]
    assert "do not read this" not in json.dumps(sent)
    assert original.read_text() == "do not read this" and len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"diff": DIFF, "can_patch": True, "explanation": "x", "execute": "shell"},
    {"diff": DIFF.replace("src/editor.js", "other.js"), "can_patch": True, "explanation": "x"},
    {"diff": DIFF, "can_patch": False, "explanation": "x"},
    {"diff": "--- a/src/editor.js\n+++ b/src/editor.js\n@@ -" + "9" * 5000 + ",1 +1,1 @@\n-x\n+y\n",
     "can_patch": True, "explanation": "x"},
])
async def test_bad_model_diff_is_not_returned_as_a_proposal(tmp_path, payload):
    result = await propose_patch(settings(tmp_path), CX, [{"path": "src/editor.js", "content": SOURCE}], True,
                                 transport=fake_patch(payload, []))
    assert result["status"] == "rejected" and result["diff"] == ""
