"""Recorded Pages samples must be genuine, reviewed and safely named."""
import json
import pytest
from scripts import publish_recorded_scan as publish


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
