"""Customer-facing standalone report assertions."""
from pathlib import Path
from aksharacheck.report import write_reports

def test_report_marks_unattempted_repairs_neutrally(tmp_path: Path):
    finding={
      "id":"f1","url":"https://example.org","viewport":390,
      "viewports":[390,1440],"selector":'[data-akshara-id="ak-1234"]',
      "sample":"ह िंदी","detector":"broken-cluster","severity":"error",
      "evidence":{"invalid_sequences":[{"codepoints":["U+093F"]}]},
      "fix":None,
    }
    data={"target":"https://example.org","summary":{"error":1,"warning":0,"info":0},"findings":[finding]}
    write_reports(data,tmp_path)
    page=(tmp_path/"report.html").read_text(encoding="utf-8")
    assert "No repair requested" in page
    assert 'class="verify neutral"' in page
    assert "Phone + Desktop" in page
    assert "390px" not in page
    assert "Show measured evidence" in page
    assert '\u2014' not in page
    assert (tmp_path/"report.md").exists()
    assert (tmp_path/"report.json").exists()

def test_verified_status_is_earned(tmp_path: Path):
    finding={
      "id":"f2","url":"https://example.org","viewport":390,
      "selector":'[data-akshara-id="ak-5678"]',
      "sample":"कನ್ನಡ","detector":"possible-clipping","severity":"warning",
      "evidence":{"scroll_height":44,"client_height":17},
      "fix":{"status":"verified","css":{"height":"auto"}},
    }
    data={"target":"https://example.org","summary":{"error":0,"warning":1,"info":0},"findings":[finding]}
    write_reports(data,tmp_path)
    page=(tmp_path/"report.html").read_text(encoding="utf-8")
    assert "Verified in Chromium" in page
    assert 'class="verify ok"' in page
