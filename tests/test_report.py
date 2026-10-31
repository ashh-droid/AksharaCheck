"""The report shows the proof on the card, uses one severity vocabulary and works offline."""
import json
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
    assert "What BharatCode says" in body
    assert '<p class="pane p-en">The box is shorter than its text.</p>' in body
    assert '<p class="pane p-hi" lang="hi">डिब्बा पाठ से छोटा है।</p>' in body
    assert '<p class="pane p-kn" lang="kn">ಪೆಟ್ಟಿಗೆ ಪಠ್ಯಕ್ಕಿಂತ ಚಿಕ್ಕದು.</p>' in body
    # One language at a time: English is chosen, and each card has its own switch.
    assert 'type="radio" name="l-abc123" id="l-abc123-en" checked' in body
    assert '<label for="l-abc123-hi" class="tab-hi" lang="hi">हिंदी</label>' in body
    css = page.split("<style>")[1].split("</style>")[0]
    assert ".panes .pane{display:none}.panes .p-en{display:block}" in css
    assert "@media print{.panes .pane{display:block!important}" in css
    assert "BharatCode <code>qwen-3.8-27b</code> explained 1 of the 1 findings to fix or check (3 model calls, 2,500 tokens, 6.5 s)." in page


def test_verified_fix_shows_before_after_and_every_attempt(tmp_path):
    png(tmp_path / "element-abc123-390.png", 300, 60)
    png(tmp_path / "element-abc123-390-fixed.png", 300, 90)
    page = render(tmp_path, [finding(
        element_screenshot="element-abc123-390.png",
        fix={"status": "verified", "css": {"height": "auto"}, "viewport": 390,
             "after_screenshot": "element-abc123-390-fixed.png",
             "attempts": [{"css": {"height": "1px"}, "attributes": {}, "status": "unverified", "reason": "Visible text area shrunk"},
                          {"css": {"height": "auto"}, "attributes": {}, "status": "verified", "reason": ""}]})])
    assert "Fix ready, tested in Chromium at 390 px" in page
    assert "Ask your developer to add this CSS to the element." in page
    assert '<img src="element-abc123-390.png" alt="The element as Chromium drew it"><figcaption>Before the fix</figcaption>' in page
    assert '<img src="element-abc123-390-fixed.png" alt="The element after the fix">' in page
    assert '<details class="attempts"><summary>BharatCode tried 2 repairs. Chromium rejected 1 before one passed.</summary>' in page
    assert "Rejected: Visible text area shrunk" in page
    assert "height: auto;" in page


def test_failure_does_not_claim_verified(tmp_path):
    page = render(tmp_path, [finding(fix={"status": "unverified", "reason": "Original issue still present",
                                          "attempts": [{"css": {"line-height": "1.8"}, "attributes": {}, "status": "unverified",
                                                        "reason": "Original issue still present"}]})])
    assert "No suggested fix passed in Chromium: original issue still present." in page
    assert "What to change" in page
    assert "Fix ready" not in page
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
    assert '<div class="figures"><figure><img src="element-good.png"' in page
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


def test_model_text_in_the_wrong_script_or_with_selectors_is_cleaned(tmp_path):
    page = render(tmp_path, [finding(
        ai_explanation='The element selected by [data-akshara-id="ak-29ef8dc6"] has a fixed height.',
        summary_hi="ಈ ಪಠ್ಯ ಕನ್ನಡದಲ್ಲಿದೆ.",  # Kannada in the Hindi slot
        summary_kn="ಈ ಪಠ್ಯ ಕನ್ನಡದಲ್ಲಿದೆ.")])
    body = page.split('<details class="more"')[0]
    assert "The element has a fixed height." in body
    assert "data-akshara-id" not in body and "ak-29ef8dc6" not in body
    assert 'class="pane p-hi"' not in body
    assert '<p class="pane p-kn" lang="kn">ಈ ಪಠ್ಯ ಕನ್ನಡದಲ್ಲಿದೆ.</p>' in body


def test_unavailable_model_placeholder_is_not_shown_as_an_explanation(tmp_path):
    page = render(tmp_path, [finding(ai_explanation="BharatCode unavailable; browser findings remain available")])
    assert "What BharatCode says" not in page


def test_language_fix_does_not_show_identical_before_and_after(tmp_path):
    png(tmp_path / "element-abc123-390.png", 300, 60)
    png(tmp_path / "element-abc123-390-fixed.png", 300, 60)
    page = render(tmp_path, [finding(detector="wrong-lang", evidence={"script": "devanagari", "effective": "en"},
        element_screenshot="element-abc123-390.png",
        fix={"status": "verified", "css": {}, "attributes": {"lang": "hi"}, "viewport": 390,
             "after_screenshot": "element-abc123-390-fixed.png"})])
    assert "element-abc123-390-fixed.png" not in page.split("<script")[0]
    assert "screen readers treat the text as Hindi" in page
    assert "Tagged as English (en), but written in Devanagari." in page


def test_overlapping_broken_sequences_are_merged(tmp_path):
    page = render(tmp_path, [finding(severity="error", detector="broken-cluster", evidence={"invalid_sequences": [
        {"position": 8, "sequence": "माा", "codepoints": ["U+092E", "U+093E", "U+093E"], "reason": "dependent vowel sign without a preceding consonant"},
        {"position": 9, "sequence": "ााि", "codepoints": ["U+093E", "U+093E", "U+093F"], "reason": "dependent vowel sign without a preceding consonant"}]})])
    assert page.count('<span class="glyph"') == 1
    assert "U+092E U+093E U+093E U+093F" in page


def test_font_findings_name_the_file_and_the_fonts(tmp_path):
    page = render(tmp_path, [
        finding(id="f1", severity="error", detector="font-load-failed", sample="", selector="document",
                evidence={"font_url": "https://example.org/fonts/missing.woff2", "status": 404}),
        finding(id="f2", severity="info", detector="font-fallback",
                evidence={"requested": "Mukta", "actual": [{"familyName": "Noto Sans Devanagari"}]}),
        finding(id="f3", detector="legacy-font", evidence={"computed_font": '"KrutiDev 010", serif'}),
    ])
    assert "https://example.org/fonts/missing.woff2" in page and "The font file returned HTTP 404." in page
    assert "The page asked for Mukta, but Chromium drew this text with Noto Sans Devanagari." in page
    assert "Font used: KrutiDev 010." in page


def test_overview_lists_every_kind_with_links(tmp_path):
    page = render(tmp_path, [finding(), finding(id="b", severity="error", detector="broken-cluster", evidence={})])
    assert '<h2 id="overview-title">What was found</h2>' in page
    assert '<a href="#broken-cluster">Broken letters</a>' in page and 'id="broken-cluster"' in page
    assert '<a href="#possible-clipping">Letters may be cut off</a>' in page


def test_json_does_not_repeat_findings_inside_pages(tmp_path):
    import json
    item = finding()
    render(tmp_path, [item], pages=[{"url": "https://example.org", "viewport": 390, "findings": [item]}])
    saved = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert "findings" not in saved["pages"][0] and saved["pages"][0]["finding_count"] == 1
    assert len(saved["findings"]) == 1


def test_duration_reads_naturally():
    from aksharacheck.report import _duration
    assert _duration(6.5) == "6.5 s" and _duration(42.2) == "42 s" and _duration(110.15) == "1 min 50 s"


def test_overview_explains_its_labels_in_plain_words(tmp_path):
    page = render(tmp_path, [
        finding(severity="error", detector="broken-cluster", evidence={"invalid_sequences": []}),
        finding(id="w", fix={"status": "verified", "css": {"height": "auto"}, "viewport": 390}),
    ])
    assert '<dl class="key"' in page
    assert "Readers see broken text. Start here." in page
    assert '<span class="state">Edit the text</span>' in page
    assert '<span class="state ok"><svg class="ico"' in page and 'Fix ready</span>' in page
    assert "✓" not in page.split("<style>")[0] + page.split("</style>")[1]
    assert "Seen on phone" in page


def test_card_sections_are_labelled_and_reasons_are_plain(tmp_path):
    page = render(tmp_path, [finding(severity="error", detector="broken-cluster", evidence={"invalid_sequences": [
        {"position": 3, "sequence": "मा ा", "codepoints": ["U+092E", "U+093E", "U+0020", "U+093E"],
         "reason": "dependent vowel sign without a preceding consonant"}]})])
    assert '<div class="evidence no-figures"><div class="ev-text"><p class="label">On the page</p>' in page
    assert "A vowel sign with no letter before it" in page
    assert "dependent vowel sign without" not in page.split("<details")[0]
    assert '<div class="steps">' in page and '<p class="todo-title">What to change</p>' in page


def test_screenshot_sits_under_the_text_at_natural_size(tmp_path):
    png(tmp_path / "element-abc123-390.png", 640, 120)
    page = render(tmp_path, [finding(element_screenshot="element-abc123-390.png")])
    evidence = page.split('<div class="evidence')[1].split('<div class="steps">')[0]
    assert 'src="element-abc123-390.png"' in evidence
    assert "How Chromium drew it at 390 px" in evidence
    css = page.split("<style>")[1].split("</style>")[0]
    assert ".figures img{display:block;width:auto;height:auto;max-width:100%;max-height:420px;margin:auto}" in css
    assert ".glyph{flex:none;display:inline-flex;align-items:center;justify-content:center;" in css


def test_report_discloses_resumed_bharatcode_work(tmp_path):
    page=render(tmp_path,[finding(
        ai_explanation="The language tag does not match.",
        summary_hi="भाषा का टैग गलत है।",
        summary_kn="ಭಾಷಾ ಗುರುತು ತಪ್ಪಾಗಿದೆ.",
        ai_resumed=True,
        fix={"status":"verified","attributes":{"lang":"hi"},"viewport":390},
    )],ai={"model":"qwen-3.8-27b","calls":0,"resumed_findings":1})
    assert "explained 1 of the 1 findings to fix or check. 1 explanation comes from an earlier run; its fixes were tested again in Chromium." in page
    md=(tmp_path/"report.md").read_text(encoding="utf-8")
    assert "BharatCode qwen-3.8-27b explained 1 of the 1 findings to fix or check. 1 explanation comes from an earlier run" in md


def test_partial_ai_report_is_visibly_labelled_in_html_and_markdown(tmp_path):
    page=render(tmp_path,[finding(fix={"status":"unavailable","reason":"BharatCode response failed"})],
                ai={"model":"qwen-3.8-27b","partial":True,
                    "requested_findings":3,"completed_findings":2,
                    "resumed_findings":2,"calls":0})
    assert "BharatCode stopped early." in page
    assert "It finished 2 of the 3 findings it was asked about." in page
    assert "BharatCode could not answer for this one" in page
    md=(tmp_path/"report.md").read_text(encoding="utf-8")
    assert "BharatCode stopped early: it finished 2 of the 3 findings it was asked about." in md


def test_findings_the_model_was_not_asked_about_say_so(tmp_path):
    page = render(tmp_path, [
        finding(ai_explanation="The box is too short.", summary_hi="डिब्बा छोटा है।", summary_kn="ಪೆಟ್ಟಿಗೆ ಚಿಕ್ಕದು.",
                fix={"status": "verified", "css": {"height": "auto"}, "viewport": 390}),
        finding(id="b", severity="error", detector="broken-cluster", evidence={"invalid_sequences": []}),
    ], ai={"model": "qwen-3.8-27b", "calls": 1})
    assert "explained 1 of the 2 findings to fix or check" in page
    assert "BharatCode was not asked about this one in this run." in page


def test_header_has_large_name_and_matching_download_buttons(tmp_path):
    page = render(tmp_path, [finding()])
    css = page.split("<style>")[1].split("</style>")[0]
    assert ".brand-name{font-size:30px;" in css
    assert 'data-file="md" aria-label="Download Markdown"><svg class="ico"' in page
    assert '<span class="dl-word">Download </span>JSON' in page


def test_download_buttons_carry_their_files_and_hide_internal_handles(tmp_path):
    page = render(tmp_path, [finding(sample="</script><b>x</b>")], generated_at="2026-10-30T19:15:48+00:00")
    assert 'download="aksharacheck-report-2026-10-30.md" data-file="md"' in page
    assert 'download="aksharacheck-report-2026-10-30.json" data-file="json"' in page
    embedded = page.split('<script type="application/json" id="report-files">')[1].split("</script>")[0]
    files = json.loads(embedded)
    assert files["md"] == (tmp_path / "report.md").read_text(encoding="utf-8")
    assert files["json"] == (tmp_path / "report.json").read_text(encoding="utf-8")
    assert "</script><b>" not in embedded
    assert "data-akshara-id" not in page.split("<script")[0]
    assert "data-akshara-id" not in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_language_selector_sync_and_optional_storage_script(tmp_path):
    page = render(tmp_path, [
        finding(id="one", ai_explanation="First explanation",
                summary_hi="पहली भाषा की व्याख्या।", summary_kn="ಮೊದಲ ವಿವರಣೆ."),
        finding(id="two", ai_explanation="Second explanation",
                summary_hi="दूसरी भाषा की व्याख्या।", summary_kn="ಎರಡನೇ ವಿವರಣೆ."),
    ], ai={"model": "qwen-3.8-27b", "calls": 2})
    assert page.count("class=\"ai\"") == 2
    assert 'aksharacheck-report-language' in page
    assert 'document.querySelectorAll(".ai input.t-"+lang)' in page
    assert 'localStorage.setItem(key,code)' in page
    assert 'try{localStorage.getItem' not in page  # storage access is guarded by a try/catch
    assert 'try{setLanguage(localStorage.getItem(key)||"en")}catch(e){}' in page


def test_html_report_includes_standalone_aksharacheck_tab_icon(tmp_path):
    import base64
    from html.parser import HTMLParser
    from aksharacheck.report import REPORT_FAVICON_SVG

    page = render(tmp_path, [finding()])
    class IconParser(HTMLParser):
        icons = []
        def handle_starttag(self, tag, attrs):
            if tag == "link":
                data = dict(attrs)
                if data.get("rel") == "icon":
                    self.icons.append(data)
    parser = IconParser()
    parser.feed(page)
    assert len(parser.icons) == 1
    icon = parser.icons[0]
    assert icon["type"] == "image/svg+xml"
    prefix = "data:image/svg+xml;base64,"
    assert icon["href"].startswith(prefix)
    decoded = base64.b64decode(icon["href"][len(prefix):]).decode("utf-8")
    assert decoded == REPORT_FAVICON_SVG
    assert 'viewBox="0 0 32 32"' in decoded
    assert "AksharaCheck report" in page


def test_local_page_cover_and_readable_addresses(tmp_path):
    page = render(tmp_path, [finding(url="http://127.0.0.1:49205/index.html", severity="info")],
                  target="http://127.0.0.1:49205/index.html")
    assert '<h1 id="report-title">Local test page</h1>' in page
    assert "served from 127.0.0.1:49205/index.html on the scanning computer" in page
    assert 'href="http://127.0.0.1' not in page
    # Only the labels this report uses are explained.
    assert "Worth knowing" in page and "Readers see broken text" not in page
    wiki = render(tmp_path / "w", [finding(url="https://hi.wikipedia.org/wiki/%E0%A4%AE%E0%A5%81%E0%A4%96")],
                  target="https://hi.wikipedia.org/")
    assert ">https://hi.wikipedia.org/wiki/मुख</a>" in wiki


def test_rendering_a_saved_report_keeps_its_page_counts(tmp_path):
    render(tmp_path, [finding()], pages=[{"url": "https://example.org", "viewport": 390, "findings": [finding()]}])
    saved = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert saved["pages"][0]["finding_count"] == 1
    write_reports(saved, tmp_path)
    again = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert again["pages"][0]["finding_count"] == 1


def test_clean_scan_displays_real_viewport_coverage_and_linked_screenshots(tmp_path):
    png(tmp_path / "page-01-390.png",390,800)
    png(tmp_path / "page-01-1440.png",1440,900)
    pages=[
        {"url":"https://ddnews.gov.in/","viewport":390,"screenshot":"page-01-390.png",
         "nodes_checked":162,"finding_count":0},
        {"url":"https://ddnews.gov.in/","viewport":1440,"screenshot":"page-01-1440.png",
         "nodes_checked":213,"finding_count":0},
    ]
    page=render(tmp_path,[],target="https://ddnews.gov.in/",pages=pages)
    assert 'id="clean-evidence-title"' in page
    assert "375 text-element checks across 2 captured viewports" in page
    assert "162 sampled text elements" in page and "213 sampled text elements" in page
    for image in ("page-01-390.png","page-01-1440.png"):
        assert 'href="'+image+'"' in page
        assert 'src="'+image+'"' in page
    assert "Indic character sequences" in page
    assert "Language tags and mixed scripts" in page
    assert "Overflow and possible clipping" in page
    assert "Font loading and rendered font names" in page
    assert "Unusually tight line spacing" in page
    assert "No BharatCode model calls were needed" in page
    saved=json.loads((tmp_path/"report.json").read_text(encoding="utf-8"))
    assert [p["nodes_checked"] for p in saved["pages"]]==[162,213]
    assert [p["finding_count"] for p in saved["pages"]]==[0,0]


def test_clean_report_does_not_reference_missing_or_unsafe_page_images(tmp_path):
    pages=[{"viewport":390,"url":"https://example.org/","screenshot":"../../secrets.png","nodes_checked":5}]
    page=render(tmp_path,[],pages=pages)
    assert 'src="../../secrets.png"' not in page
    assert "No saved page screenshot available" in page


def test_unscanned_viewport_is_not_called_clean(tmp_path):
    page=render(tmp_path,[],pages=[
        {"viewport":390,"url":"https://example.org/","error":"timeout"},
        {"viewport":1440,"url":"https://example.org/","nodes_checked":4}
    ])
    assert "No findings in completed checks; some viewports were not scanned." in page
    assert "Do not treat missing results as a clean pass." in page
    assert 'id="clean-evidence-title"' not in page
    assert '<p class="clean">' not in page


def test_many_places_from_one_parent_tag_are_explained_once_and_folded(tmp_path):
    items = [finding(id=f"k{i}", detector="wrong-lang", sample="ಕರ್ನಾಟಕ ವಾರ್ತೆ " + str(i),
                     evidence={"script": "kannada", "effective": "en", "lang_source": "html"}) for i in range(8)]
    page = render(tmp_path, items)
    assert "All 8 places take their language from the page&#x27;s &lt;html&gt; element, which says lang=&quot;en&quot;." in page
    assert 'marking the Kannada sections with lang=&quot;kn&quot;' in page
    assert '<span class="state">One tag to change</span>' in page
    assert '<details class="more-cards"><summary>Show the other 5 places</summary>' in page
    assert page.count('<article class="card') == 8


def test_short_lists_are_not_folded_and_own_tags_are_not_called_shared(tmp_path):
    items = [finding(id=f"s{i}", detector="wrong-lang", evidence={"script": "devanagari", "effective": "en", "lang_source": "self"})
             for i in range(4)]
    page = render(tmp_path, items)
    assert "more-cards" not in page.split("<style>")[0] + page.split("</style>")[1]
    assert 'class="shared"' not in page
