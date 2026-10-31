"""Open a rendered report in Chromium at five widths with scripts/check_report_ui.py."""
import importlib.util
import struct
import zlib
from pathlib import Path

import pytest

from aksharacheck.report import write_reports

ROOT = Path(__file__).resolve().parents[1]


def png(path, width, height):
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def test_report_layout_in_chromium(tmp_path):
    pytest.importorskip("playwright.sync_api")
    spec = importlib.util.spec_from_file_location("check_report_ui", ROOT / "scripts" / "check_report_ui.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    png(tmp_path / "element-a-390.png", 640, 90)
    png(tmp_path / "element-a-390-fixed.png", 640, 140)
    findings = [
        {"id": "a", "url": "https://example.org", "viewport": 390, "viewports": [390, 1440], "selector": '[data-akshara-id="ak-1"]',
         "sample": "कृपया पूरा पाठ दिखाएं", "detector": "possible-clipping", "severity": "warning", "confidence": "suspected",
         "evidence": {"overflow_pixels": 40}, "element_screenshot": "element-a-390.png",
         "ai_explanation": "The box is shorter than its text.", "summary_hi": "डिब्बा पाठ से छोटा है।", "summary_kn": "ಪೆಟ್ಟಿಗೆ ಚಿಕ್ಕದು.",
         "fix": {"status": "verified", "css": {"height": "auto"}, "viewport": 390, "after_screenshot": "element-a-390-fixed.png",
                 "attempts": [{"css": {"height": "1px"}, "attributes": {}, "status": "unverified", "reason": "Visible text area shrunk"},
                              {"css": {"height": "auto"}, "attributes": {}, "status": "verified", "reason": ""}]}},
        {"id": "b", "url": "https://example.org", "viewport": 390, "viewports": [390], "selector": '[data-akshara-id="ak-2"]',
         "sample": "ಇದು ಕಾ ಪರೀಕ್ಷೆ", "detector": "broken-cluster", "severity": "error", "confidence": "confirmed",
         "evidence": {"invalid_sequences": [{"position": 3, "sequence": "ಕಾ ಿ", "codepoints": ["U+0C95", "U+0CBE", "U+0020", "U+0CBF"],
                                             "reason": "dependent vowel sign without a preceding consonant"}]},
         "ai_explanation": "The vowel sign is separated from its letter.",
         "summary_hi": "यहाँ स्वर चिह्न गलत जगह पर है।",
         "summary_kn": "ಸ್ವರ ಗುರುತು ತಪ್ಪು ಸ್ಥಾನದಲ್ಲಿದೆ."},
    ]
    write_reports({"target": "https://example.org", "engine_version": "test", "findings": findings, "pages": [],
                   "ai": {"model": "qwen-3.8-27b", "calls": 3, "input_tokens": 100, "output_tokens": 50, "seconds": 4}}, tmp_path)
    try:
        module.check(tmp_path / "report.html")
    except Exception as exc:  # A machine without a usable Chromium cannot run this check.
        if "Executable doesn't exist" in str(exc) or "playwright install" in str(exc):
            pytest.skip("Chromium for Playwright is not installed")
        raise
