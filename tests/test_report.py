"""Reader-first report tests: clarity, file safety and honest verification state."""
from pathlib import Path
from aksharacheck.report import write_reports


def example_finding(**updates):
    return {
        "id":"abc123","url":"https://example.org",
        "viewport":390,"viewports":[390,1440],
        "selector":'[data-akshara-id="ak-1234"]',
        "sample":"सामग्री पर जाएँ",
        "detector":"possible-clipping","severity":"warning",
        "confidence":"suspected",
        "evidence":{"scroll_height":63,"client_height":1,"overflow_pixels":62},
        "fix":None,**updates
    }


def report(tmp_path,findings):
    counts={level:sum(f["severity"]==level for f in findings) for level in ("error","warning","info")}
    data={"target":"https://example.org","summary":counts,"pages":[],"findings":findings}
    write_reports(data,tmp_path)
    return (tmp_path/"report.html").read_text(encoding="utf-8")


def test_compact_honest_report(tmp_path):
    page=report(tmp_path,[example_finding()])
    assert "What the browser found." in page
    assert "Potential rendering issues" in page
    assert "Phone + Desktop" in page
    assert "Suspected, review needed" in page
    assert "No repair requested" not in page
    assert "No AI explanation has been requested" not in page
    assert "Inspect details and suggested next step" in page
    assert "This is an indicator, not visual proof" in page
    assert "JSON report" in page and "Markdown" in page
    assert '\u2014' not in page
    assert (tmp_path/"report.json").exists()
    assert (tmp_path/"report.md").exists()


def test_verified_state_requires_explicit_verdict(tmp_path):
    item=example_finding()
    item["fix"]={"status":"verified","css":{"height":"auto"}}
    page=report(tmp_path,[item])
    assert "Independently verified in Chromium" in page
    assert 'class="repair verified"' in page
    assert "height: auto;" in page


def test_failed_and_missing_verification_not_green(tmp_path):
    item=example_finding()
    item["fix"]={"status":"unverified","reason":"Text moved offscreen"}
    page=report(tmp_path,[item])
    assert "did not pass verification" in page
    assert 'class="repair verified"' not in page


def test_untrusted_page_is_escaped(tmp_path):
    item=example_finding()
    item["sample"]='<img src=x onerror="alert(1)">'
    item["url"]="https://example.org/?q=%3Cscript%3E"
    page=report(tmp_path,[item])
    assert '<img src=x onerror=' not in page
    assert '&lt;img src=x' in page
    assert '<script' not in page


def test_no_tiny_or_missing_image_tiles(tmp_path):
    item=example_finding()
    item["element_screenshot"]="element-small.png"
    item["screenshot"]="page-01-390.png"
    # Minimal PNG IHDR bytes establish size for display logic; report does not decode the image.
    (tmp_path/"element-small.png").write_bytes(
        b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" +
        (480).to_bytes(4,"big") + (1).to_bytes(4,"big")
    )
    (tmp_path/"page-01-390.png").write_bytes(b"placeholder")
    page=report(tmp_path,[item])
    assert '<img src="element-small.png"' not in page
    assert "Open browser screenshot" in page
    assert "page-01-390.png" in page


def test_offline_development_mode_labeled(tmp_path):
    item=example_finding()
    data={"target":"https://example.org","summary":{"error":0,"warning":1,"info":0},
          "pages":[],"findings":[item],"demo_mode":True}
    write_reports(data,tmp_path)
    page=(tmp_path/"report.html").read_text(encoding="utf-8")
    assert "Offline engineering demonstration" in page
    assert "No BharatCode API was called" in page
