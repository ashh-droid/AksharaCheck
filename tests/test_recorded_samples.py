"""Recorded Pages samples must be genuine, reviewed and safely named."""
import json
import pytest
import importlib.util
from pathlib import Path

# Import this development-only publisher by file path. The scripts folder
# is not installed as a Python application package in CI.
_path=Path(__file__).resolve().parents[1]/"scripts"/"publish_recorded_scan.py"
_spec=importlib.util.spec_from_file_location("publish_recorded_scan",_path)
assert _spec and _spec.loader
publish=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publish)


def test_rejects_private_scans():
    assert not publish.public_url("http://127.0.0.1:8000")
    assert not publish.public_url("http://localhost:8000")
    assert not publish.public_url("http://internal.local")
    assert not publish.public_url("javascript:alert(1)")
    assert publish.public_url("https://hi.wikipedia.org/")

def test_public_report_requires_explicit_review(tmp_path,monkeypatch):
    monkeypatch.setattr(publish,"SAMPLES",tmp_path/"samples")
    source=tmp_path/"source"
    source.mkdir()
    (source/"report.json").write_text(json.dumps({
        "target":"https://hi.wikipedia.org/","pages":[{"url":"https://hi.wikipedia.org/","viewport":390,"screenshot":"page-01-390.png"}],
        "findings":[],"summary":{"error":0,"warning":0,"info":0},
        "generated_at":"2026-10-29T21:00:00+00:00"}),encoding="utf-8")
    (source/"report.html").write_text("<h1>Recorded Chromium report</h1>",encoding="utf-8")
    (source/"report.md").write_text("# Recorded Chromium report",encoding="utf-8")
    (source/"page-01-390.png").write_bytes(b"image-test")
    with pytest.raises(ValueError,match="Review"):
        publish.copy_scan(source,"hindi-wikipedia","Hindi Wikipedia",False)
    publish.copy_scan(source,"hindi-wikipedia","Hindi Wikipedia",True)
    catalog=json.loads((tmp_path/"samples"/"catalog.json").read_text(encoding="utf-8"))
    assert catalog["scans"][0]["title"]=="Hindi Wikipedia"
    assert (tmp_path/"samples"/"hindi-wikipedia"/"page-01-390.png").is_file()
    with pytest.raises(ValueError,match="already exists"):
        publish.copy_scan(source,"hindi-wikipedia","Hindi Wikipedia",True)

def test_slug_cannot_traverse_directories(tmp_path,monkeypatch):
    monkeypatch.setattr(publish,"SAMPLES",tmp_path)
    with pytest.raises(ValueError,match="Slug"):
        publish.copy_scan(tmp_path,"../private","Test",True)


def test_publishes_fix_captures_fonts_and_gallery_details(tmp_path, monkeypatch):
    monkeypatch.setattr(publish, "SAMPLES", tmp_path / "samples")
    source = tmp_path / "scan"
    source.mkdir()
    findings = [
        {"id": "a", "severity": "warning", "detector": "possible-clipping", "sample": "कृपया पूरा पाठ",
         "element_screenshot": "element-a-390.png",
         "fix": {"status": "verified", "after_screenshot": "element-a-390-fixed.png"}},
        {"id": "b", "severity": "error", "detector": "broken-cluster", "sample": "ह िंदी", "fix": {"status": "not-applicable"}},
    ]
    (source / "report.json").write_text(json.dumps({
        "target": "https://kn.wikipedia.org/", "pages": [{"url": "https://kn.wikipedia.org/", "viewport": 390}],
        "findings": findings, "summary": {"error": 1, "warning": 1, "info": 0},
        "ai": {"model": "qwen-3.8-27b", "calls": 4}, "generated_at": "2026-11-02T10:00:00+00:00"}), encoding="utf-8")
    for name in ("report.html", "report.md", "element-a-390.png", "element-a-390-fixed.png", "font-anek-latin-400.woff2"):
        (source / name).write_bytes(b"x")
    publish.copy_scan(source, "kannada-wikipedia", "Kannada Wikipedia", True)
    out = tmp_path / "samples" / "kannada-wikipedia"
    assert (out / "element-a-390-fixed.png").is_file()
    assert (out / "font-anek-latin-400.woff2").is_file()
    entry = json.loads((tmp_path / "samples" / "catalog.json").read_text(encoding="utf-8"))["scans"][0]
    assert entry["ai_calls"] == 4 and entry["verified_fixes"] == 1
    assert entry["highlight"] == {"detector": "broken-cluster", "sample": "ह िंदी"}


def test_fixture_is_explicitly_marked_and_other_local_urls_remain_blocked(tmp_path,monkeypatch):
    monkeypatch.setattr(publish,"SAMPLES",tmp_path/"samples")
    source=tmp_path/"demo"
    source.mkdir()
    demo_url="http://127.0.0.1:8765/index.html"
    payload={"target":demo_url,
             "pages":[{"url":demo_url,"viewport":390}],
             "findings":[{"id":"one","severity":"warning",
                          "detector":"wrong-lang","sample":"हिंदी",
                          "fix":{"status":"verified"}}],
             "summary":{"error":0,"warning":1,"info":0},
             "generated_at":"2026-10-31T01:00:00+05:30",
             "ai":{"model":"qwen-3.8-27b","calls":1}}
    (source/"report.json").write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
    (source/"report.html").write_text("<h1>Local demo</h1>",encoding="utf-8")
    (source/"report.md").write_text("# Local demo",encoding="utf-8")

    with pytest.raises(ValueError,match="public web pages"):
        publish.copy_scan(source,"local-demo","Local demo",True)
    with pytest.raises(ValueError,match="Review"):
        publish.copy_scan(source,"local-demo","Local demo",False,fixture_demo=True)
    publish.copy_scan(source,"local-demo","Local demo",True,fixture_demo=True)
    saved=json.loads((tmp_path/"samples"/"catalog.json").read_text(encoding="utf-8"))["scans"][0]
    assert saved["kind"]=="fixture"
    assert saved["verified_fixes"]==1

    payload["target"]="http://127.0.0.1:8765/admin"
    (source/"report.json").write_text(json.dumps(payload),encoding="utf-8")
    with pytest.raises(ValueError,match="local /index.html"):
        publish.copy_scan(source,"other-private","Other",True,fixture_demo=True)
    assert not publish.fixture_demo_url("http://192.168.1.3:8765/index.html")
    assert not publish.fixture_demo_url("http://127.0.0.1:8765/private")
