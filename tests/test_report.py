"""The report shows the proof on the card, uses one severity vocabulary and works offline."""
import re

from aksharacheck.report import FONT_FILES, write_reports


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


def png(path, width, height):
    # Only the PNG header is read for dimensions.
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + width.to_bytes(4, "big") + height.to_bytes(4, "big"))


def render(tmp_path, findings, **changes):
    data = {
        "target": "https://example.org/notices",
        "engine_version": "2026-10-29-visibility-v2",
        "generated_at": "2026-10-29T14:00:00+00:00",
        "pages": [],
        "findings": findings,
        "summary": {kind: sum(f["severity"] == kind for f in findings) for kind in ("error", "warning", "info")},
    }
    data.update(changes)
    write_reports(data, tmp_path)
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.md").exists()
    return (tmp_path / "report.html").read_text(encoding="utf-8")


def test_one_severity_vocabulary_and_a_plain_summary(tmp_path):
    page = render(tmp_path, [
        finding(id="e1", severity="error", detector="broken-cluster",
                evidence={"invalid_sequences": [{"sequence": "ह ि", "codepoints": ["U+0939", "U+0020", "U+093F"],
                                                 "reason": "dependent vowel sign without a preceding consonant"}]}),
        finding(),
        finding(id="n1", severity="info", detector="font-fallback", evidence={"requested": "Mukta"}),
    ])
    assert "1 problem to fix, 1 thing to check and 1 note." in page
    for word in (">To fix <", ">To check <", ">Notes <", '<span class="sev">Fix</span>', '<span class="sev">Check</span>'):
        assert word in page
    for old in ("Potential", "Observation", "Warnings", "FINDINGS SUMMARY", "Every letter matters", "occurrence"):
        assert old not in page
    assert "U+0939 U+0020 U+093F" in page
    assert "Checked in Chromium at phone (390 px) and desktop (1440 px) on 29 Oct 2026, 14:00 UTC." in page


def test_no_generated_dashboard_habits(tmp_path):
    page = render(tmp_path, [finding(), finding(id="b", sample="मुख्य मेन्यू")])
    css = page.split("<style>")[1].split("</style>")[0]
    assert "text-transform:uppercase" not in css
    assert "letter-spacing:.1" not in css
    assert not re.search(r"font-weight:(7|8)\d\d", css)
    assert "score-panel" not in page and "group-accent" not in page and "finding-number" not in page
    assert "2 places" in page
    assert "—" not in page


def test_bharatcode_explanation_and_translations_are_on_the_card(tmp_path):
    page = render(tmp_path, [finding(
        ai_explanation="The box is shorter than its text.",
        summary_hi="डिब्बा पाठ से छोटा है।", summary_kn="ಪೆಟ್ಟಿಗೆ ಪಠ್ಯಕ್ಕಿಂತ ಚಿಕ್ಕದು.")],
        ai={"model": "qwen-3.8-27b", "calls": 3, "input_tokens": 2000, "output_tokens": 500, "seconds": 6.5})
    body = page.split("<details")[0]  # visible without opening anything
    assert "BharatCode explanation" in body
    assert "The box is shorter than its text." in body
    assert '<span lang="hi">डिब्बा पाठ से छोटा है।</span>' in body
    assert '<span lang="kn">ಪೆಟ್ಟಿಗೆ ಪಠ್ಯಕ್ಕಿಂತ ಚಿಕ್ಕದು.</span>' in body
    assert "BharatCode <code>qwen-3.8-27b</code>: 3 calls, 2,500 tokens, 6.5 s." in page


def test_verified_fix_shows_before_after_and_every_attempt(tmp_path):
    png(tmp_path / "element-abc123-390.png", 300, 60)
    png(tmp_path / "element-abc123-390-fixed.png", 300, 90)
    page = render(tmp_path, [finding(
        element_screenshot="element-abc123-390.png",
        fix={"status": "verified", "css": {"height": "auto"}, "viewport": 390,
             "after_screenshot": "element-abc123-390-fixed.png",
             "attempts": [{"css": {"height": "1px"}, "attributes": {}, "status": "unverified", "reason": "Visible text area shrunk"},
                          {"css": {"height": "auto"}, "attributes": {}, "status": "verified", "reason": ""}]})])
    assert "Fix verified in a fresh Chromium at 390 px" in page
    assert '<img src="element-abc123-390.png" alt="The element before the fix">' in page
    assert '<img src="element-abc123-390-fixed.png" alt="The element after the fix">' in page
    assert "BharatCode suggested 2 repairs, and Chromium tested each one" in page
    assert "Rejected: Visible text area shrunk" in page
    assert "height: auto;" in page


def test_failure_does_not_claim_verified(tmp_path):
    page = render(tmp_path, [finding(fix={"status": "unverified", "reason": "Original issue still present",
                                          "attempts": [{"css": {"line-height": "1.8"}, "attributes": {}, "status": "unverified",
                                                        "reason": "Original issue still present"}]})])
    assert "No suggested fix passed. Original issue still present." in page
    assert "Fix verified" not in page
    assert "repair ok" not in page


def test_text_errors_get_a_content_instruction(tmp_path):
    page = render(tmp_path, [finding(severity="error", detector="broken-cluster", evidence={"invalid_sequences": []},
                                     fix={"status": "not-applicable", "reason": "No automatic repair"})])
    assert "What to change" in page
    assert "CSS cannot repair it" in page


def test_crops_show_on_the_card_and_slivers_do_not(tmp_path):
    png(tmp_path / "element-good.png", 320, 60)
    png(tmp_path / "element-sliver.png", 480, 1)
    (tmp_path / "page-01-390.png").write_bytes(b"placeholder")
    page = render(tmp_path, [
        finding(element_screenshot="element-good.png"),
        finding(id="s", element_screenshot="element-sliver.png", screenshot="page-01-390.png"),
    ])
    assert '<figure class="capture"><img src="element-good.png"' in page
    assert 'src="element-sliver.png"' not in page
    assert 'href="page-01-390.png"' in page


def test_html_escaping_and_safe_links(tmp_path):
    page = render(tmp_path, [
        finding(sample='<img src=x onerror="alert(1)">', url="https://example.org/?q=%3Cscript%3E")
    ], target="javascript:alert(1)")
    assert "<img src=x onerror=" not in page
    assert "&lt;img src=x" in page
    assert "<script>alert" not in page
    assert 'href="javascript:' not in page


def test_fonts_ship_with_the_report(tmp_path):
    page = render(tmp_path, [finding()])
    assert "fonts.googleapis" not in page
    for name in FONT_FILES:
        assert (tmp_path / name).is_file()
        assert "url('" + name + "')" in page
    assert 'content="only light"' in page


def test_demo_and_partial_scans_are_disclosed(tmp_path):
    assert "No BharatCode model call was made" in render(tmp_path, [finding()], demo_mode=True)
    page = render(tmp_path, [finding()], pages=[{"url": "https://example.org", "viewport": 390, "error": "timeout"}])
    assert "Incomplete scan." in page and "Missing data is not clean data" in page
    assert "Earlier scan data." in render(tmp_path, [finding()], engine_version=None)


def test_clean_scan_is_honest(tmp_path):
    page = render(tmp_path, [])
    assert "Nothing broke in these checks." in page
    assert "not every page on the site" in page


def test_markdown_uses_the_same_words(tmp_path):
    render(tmp_path, [finding(ai_explanation="Too short.", summary_hi="छोटा।",
                              fix={"status": "verified", "css": {"height": "auto"}, "viewport": 390})])
    md = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## To check" in md and "### Check: Letters may be cut off" in md
    assert "BharatCode: Too short." in md and "हिंदी: छोटा।" in md
    assert "Fix verified in Chromium at 390 px" in md
