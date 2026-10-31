"""Standalone evidence review must never rewrite reports or call BharatCode."""
import json
from scripts import audit_saved_reports as review


def test_custom_font_aliases_are_candidates_not_confirmed_defects():
    assert review.font_family_alias_candidate("pvtextsemibold","Prajavani Text Semibold")
    assert review.font_family_alias_candidate("Noto Sans Kannada","Noto Sans Kannada")
    assert not review.font_family_alias_candidate("Noto Sans Kannada","Arial")


def test_full_report_review_detects_false_positive_and_inherited_language(tmp_path):
    target=tmp_path/"report.json"
    source={
        "target":"https://example.org/","generated_at":"2026-10-31T14:14:00+00:00",
        "engine_version":"previous","summary":{"error":1,"warning":2,"info":1},
        "pages":[{"url":"https://example.org/","viewport":390,"screenshot":"page-01-390.png","finding_count":4}],
        "findings":[
            {"id":"broken","detector":"broken-cluster","severity":"error","viewport":390,
             "sample":"ಆ್ಯಪ್ ಡೌನ್‌ಲೋಡ್","evidence":{"invalid_sequences":[
                 {"position":1,"sequence":"ಆ್","reason":"virama without a preceding consonant"}]}},
            {"id":"lang1","detector":"wrong-lang","severity":"warning","viewport":390,
             "sample":"ಕರ್ನಾಟಕ ವಾರ್ತೆ","evidence":{"effective":"en","script":"kannada"}},
            {"id":"lang2","detector":"wrong-lang","severity":"warning","viewport":390,
             "sample":"ಸುದ್ದಿಗಳು ಮತ್ತು ಮಾಹಿತಿ","evidence":{"effective":"en","script":"kannada"}},
            {"id":"font","detector":"font-fallback","severity":"info","viewport":390,
             "sample":"ಚಂದಾದಾರರಾಗಿ","evidence":{"requested":"pvtextsemibold","actual":[
                 {"familyName":"Prajavani Text Semibold","glyphCount":12}]}},
        ],
    }
    target.write_text(json.dumps(source,ensure_ascii=False),encoding="utf-8")
    original=target.read_bytes()
    data=review.inspect(target)
    assert target.read_bytes()==original
    assert data["counts"]["match"] is True
    assert data["language_tags"]["effective_language_tags"]=={"en":2}
    assert data["broken_clusters"][0]["current_rule_still_flags"] is False
    assert data["possible_custom_font_aliases"]["count"]==1
    assert data["missing_screenshot_files"]==["page-01-390.png"]
    assert data["duplicate_finding_ids"]==0


def test_cannot_pass_a_non_report_json_file(tmp_path):
    path=tmp_path/"something.json"
    path.write_text('{"other":"data"}',encoding="utf-8")
    try:
        review.inspect(path)
    except ValueError as e:
        assert "report.json" in str(e)
    else:
        raise AssertionError("Expected rejection of non-report JSON")
