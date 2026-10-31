"""Lock the safe final public showcase: no old findings repackaged as defects."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
spec=importlib.util.spec_from_file_location("finalize_submission_showcase",
                                             ROOT/"scripts"/"finalize_submission_showcase.py")
assert spec and spec.loader
showcase=importlib.util.module_from_spec(spec)
spec.loader.exec_module(showcase)


def audited_capture():
    findings=([
        {"id":f"kn-{i}","detector":"wrong-lang","severity":"warning",
         "evidence":{"lang_source":"html","effective":"en","script":"kannada"},
         "sample":"ಕರ್ನಾಟಕ ವಾರ್ತೆ"} for i in range(72)
    ] + [{
        "id":"overflow","detector":"mobile-overflow","severity":"warning",
        "sample":"ರಾಜ್ಯ ಸುದ್ದಿ"
    }] + [{
        "id":f"font-{i}","detector":"font-fallback","severity":"info",
        "sample":"ಕರ್ನಾಟಕ"} for i in range(13)
    ])
    return {"target":showcase.TARGET,"engine_version":showcase.ENGINE,
            "summary":{"error":0,"warning":73,"info":13},
            "ai":{"calls":0},"findings":findings,
            "pages":[
                {"url":showcase.TARGET,"viewport":390,"screenshot":"page-01-390.png",
                 "nodes_checked":72},
                {"url":showcase.TARGET,"viewport":1440,"screenshot":"page-01-1440.png",
                 "nodes_checked":99}
            ]}


def test_final_kannada_capture_requires_reviewed_source_and_version(tmp_path):
    payload=audited_capture()
    for page in payload["pages"]:
        (tmp_path/page["screenshot"]).write_bytes(b"image")
    for name in ("report.html","report.json","report.md"):
        (tmp_path/name).write_text("reviewed",encoding="utf-8")
    showcase.validate(payload,tmp_path)
    payload["findings"][0]["evidence"]["lang_source"]="section"
    with pytest.raises(ValueError,match="Language-tag inheritance"):
        showcase.validate(payload,tmp_path)
    payload["findings"][0]["evidence"]["lang_source"]="html"
    payload["engine_version"]="2026-10-29-visibility-v2"
    with pytest.raises(ValueError,match="precision"):
        showcase.validate(payload,tmp_path)


def test_readme_showcase_replaces_wikipedia_but_keeps_archive_link():
    # The script migrated the README once; test it on the README as it was before.
    source=("[Hindi Wikipedia report]("+showcase.WIKI_LINK+")\n\n"
            "| [Hindi Wikipedia]("+showcase.WIKI_LINK+"), 31 Oct 2026 | "
            "0 problems, 0 to check, 3 notes (font fallback and line spacing observations). "
            "Browser checks only, no model calls. |\n\n"
            "Both reports are published exactly as AksharaCheck wrote them. Open them "
            "to see the screenshots, the character codes, every repair attempt "
            "and the Markdown and JSON downloads.\n")
    modified=showcase.replace_readme(source)
    assert "[Karnataka Varthe (Kannada) report]" in modified
    assert modified.count(showcase.NEW_LINK)==2
    assert "[DD News (Hindi)]" in modified
    assert "one HTML ancestor" in modified
    assert "| [Hindi Wikipedia](" not in modified
    assert "The earlier Hindi Wikipedia report remains available" in modified
    assert "138 tests" not in modified


def test_gallery_source_has_responsive_three_card_layout():
    css=(ROOT/"web"/"src"/"style.css").read_text(encoding="utf-8")
    page=(ROOT/"web"/"src"/"main.tsx").read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css
    assert "@media (max-width: 959px) { .recorded-grid" in css
    assert "s.review_note &&" in page
    assert "min-width: 0; display: flex; flex-direction: column" in css


def test_judge_first_readme_has_three_real_links_and_scoped_claims():
    readme=(ROOT/"README.md").read_text(encoding="utf-8")
    assert "A three-minute tour for judges" in readme
    assert "9 of 9 actionable findings explained" in readme
    assert "4 repairs verified in Chromium" in readme
    assert "No account or API key is needed." in readme
    assert "no change to the live site or screen-reader behavior was verified" in readme
    assert "an older [Hindi Wikipedia report]" in readme.lower()
    assert "72 pieces of Kannada text are announced as English" not in readme
    assert "changing that one tag fixes all 72" not in readme
    assert "All three are dated snapshots, published exactly as" not in readme
    for slug in ("akshara-fixture-demo","karnataka-varthe-kannada","dd-news-hindi"):
        url=f"https://ashh-droid.github.io/AksharaCheck/samples/{slug}/report.html"
        assert url in readme
        assert (ROOT/"web"/"public"/"samples"/slug/"report.html").is_file()


def test_showcase_publisher_does_not_undo_manually_improved_readme():
    source=(ROOT/"README.md").read_text(encoding="utf-8")
    assert showcase.replace_readme(source)==source
