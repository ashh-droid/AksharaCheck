"""Accessible, compact, truthful and offline-safe report regression tests."""
from pathlib import Path

from aksharacheck.report import write_reports


def finding(**changes):
    example = {
        "id": "abc123", "url": "https://example.org",
        "viewport": 390, "viewports": [390, 1440],
        "selector": '[data-akshara-id="ak-1234"]',
        "sample": "सामग्री पर जाएँ", "detector": "possible-clipping",
        "severity": "warning", "confidence": "suspected",
        "evidence": {"scroll_height": 63, "client_height": 1, "overflow_pixels": 62},
        "fix": None,
    }
    example.update(changes)
    return example


def render(tmp_path, findings, **changes):
    data = {
        "target": "https://example.org",
        "engine_version": "2026-10-29-visibility-v2",
        "pages": [],
        "findings": findings,
        "summary": {
            kind: sum(f["severity"] == kind for f in findings)
            for kind in ("error", "warning", "info")
        },
    }
    data.update(changes)
    write_reports(data, tmp_path)
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
    return (tmp_path / "report.html").read_text(encoding="utf-8")


def test_groups_repeated_findings_into_one_clear_section(tmp_path):
    page = render(tmp_path, [
        finding(),
        finding(id="second", sample="मुख्य मेन्यू"),
        finding(id="third", detector="font-fallback", severity="info",
                evidence={"requested": "Linux Libertine"}),
    ])
    assert "Every letter matters." in page
    assert page.count('<details class="issue-group') == 2
    assert "2 occurrences" in page
    assert "Potential" in page
    assert "Observed width" not in page
    assert page.count("The browser measured more text height") == 1
    assert page.count("View evidence and next step") == 3
    assert "Phone + Desktop" in page
    assert '<details class="issue-group info">' in page
    assert "This report has the latest design" not in page
    assert '\u2014' not in page


def test_old_saved_scan_is_marked_outdated(tmp_path):
    page = render(tmp_path, [finding()], engine_version=None)
    assert "Earlier scan data" in page
    assert "Run a fresh scan" in page


def test_verified_state_only_when_explicit(tmp_path):
    item = finding(fix={"status": "verified", "css": {"height": "auto"}})
    page = render(tmp_path, [item])
    assert "Verified after a separate browser check" in page
    assert 'class="result verified"' in page
    assert "height: auto;" in page


def test_failure_does_not_claim_verified(tmp_path):
    page = render(tmp_path, [
        finding(fix={"status": "unverified", "reason": "Text hidden"}),
        finding(id="x", fix=None, sample="दूसरी पंक्ति"),
    ])
    assert "Proposed repair failed verification" in page
    assert 'class="result verified"' not in page
    assert "No repair requested" not in page


def test_html_escaping_and_safe_links(tmp_path):
    page = render(tmp_path, [
        finding(sample='<img src=x onerror="alert(1)">',
                url="https://example.org/?q=%3Cscript%3E")
    ], target="javascript:alert(1)")
    assert '<img src=x onerror=' not in page
    assert '&lt;img src=x' in page
    assert '<script>alert' not in page
    assert 'href="javascript:' not in page


def test_bad_1px_crop_shows_link_not_empty_thumbnail(tmp_path):
    item = finding(
        element_screenshot="element-small.png",
        screenshot="page-01-390.png",
    )
    # Only the PNG header dimensions are inspected.
    (tmp_path / "element-small.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" +
        (480).to_bytes(4, "big") + (1).to_bytes(4, "big")
    )
    (tmp_path / "page-01-390.png").write_bytes(b"placeholder")
    page = render(tmp_path, [item])
    assert '<img src="element-small.png"' not in page
    assert 'href="page-01-390.png"' in page
    assert "Open browser screenshot" in page


def test_demo_is_visibly_disclosed(tmp_path):
    page = render(tmp_path, [finding()], demo_mode=True)
    assert "Offline development demo" in page
    assert "No BharatCode model call was made" in page


def test_partial_scan_warns_reader(tmp_path):
    page = render(tmp_path, [finding()],
                  pages=[{"url": "https://example.org", "viewport": 390,
                          "error": "navigation timeout"}])
    assert "Incomplete scan" in page
    assert "Missing data is not clean data" in page

def test_timestamp_and_zero_errors_are_not_alarm_colored(tmp_path):
    page = render(tmp_path, [finding()],
                  generated_at="2026-10-29T14:00:00+00:00")
    assert "Scanned 2026-10-29T14:00:00Z" in page
    assert 'class="score-num error zero"' in page
