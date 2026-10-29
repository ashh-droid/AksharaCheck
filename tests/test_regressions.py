"""Regression tests for the independent AksharaCheck code review."""
import pytest
from aksharacheck.ai import safe_declarations, safe_attributes, preserve_visible_text
from aksharacheck.detectors import malformed_clusters, run_dom_detectors, merge_findings, failed_font_findings

@pytest.mark.parametrize("text",["अि","१ि","(ि","ंभारत","का़","क््"])
def test_invalid_cluster(text):
    assert malformed_clusters(text), text

@pytest.mark.parametrize("text",["क्षत्रिय","ಕೊ","क़ि","क्\\u200dष","किं","क्क्"])
def test_valid_cluster(text):
    assert not malformed_clusters(text), text

def node(**updates):
    data={"selector":'[data-akshara-id="ak-aabbccdd"]',"text":"यह हिन्दी भाषा का उदाहरण है",
          "font":"sans-serif","lang":"hi","fontSize":20,"lineHeight":35,"lineCount":2,
          "clientWidth":200,"scrollWidth":200,"clientHeight":100,"scrollHeight":100,
          "overflowX":"visible","overflowY":"visible"}
    return {**data,**updates}

def test_devanagari_language_codes():
    for language in ["hi","mr","ne","sa","kok","mai","bho","doi","brx","sd"]:
        found=run_dom_detectors("https://example.org",390,[node(lang=language)])
        assert not any(f["detector"]=="wrong-lang" for f in found), language

def test_tulu_kannada_script():
    found=run_dom_detectors("https://example.org",390,[node(text="ಇದು ತುಳು ಭಾಷೆಗೆ ಬಳಸಬಹುದಾದ ಕನ್ನಡ ಲಿಪಿ",lang="tcy")])
    assert not any(f["detector"]=="wrong-lang" for f in found)

def test_mixed_scripts_have_own_finding():
    found=run_dom_detectors("https://example.org",390,[node(text="टूटा अक्षर · ತುಂಡಾದ ಅಕ್ಷರ",lang="en")])
    assert any(f["detector"]=="mixed-language" for f in found)
    assert not any(f["detector"]=="wrong-lang" for f in found)

def test_deduplicate_across_viewports():
    a=run_dom_detectors("https://example.org",390,[node(lang="en")])[0]
    b=run_dom_detectors("https://example.org",1440,[node(lang="en")])[0]
    assert a["id"]==b["id"]
    m=merge_findings([a,b])
    assert len(m)==1 and m[0]["viewports"]==[390,1440]

def test_deduplicate_font_failure():
    events=[{"font_url":"https://example.org/a.woff2","status":404},
            {"font_url":"https://example.org/a.woff2","error":"request failed"},
            {"font_url":"https://private/a.woff2","error":"request failed","blocked_by_scanner":True}]
    found=failed_font_findings("https://example.org",390,events)
    assert len(found)==1 and found[0]["evidence"]["status"]==404

def snapshot(**changes):
    return {"text":"यह हिन्दी भाषा का उदाहरण है","display":"block",
            "visibility":"visible","opacity":1,"fontSize":20,
            "bounds":{"x":10,"y":10,"w":200,"h":40},**changes}

@pytest.mark.parametrize("changed",[
    {"display":"none"},{"visibility":"hidden"},{"opacity":0},
    {"fontSize":1},{"bounds":{"x":10,"y":10,"w":200,"h":1}},
    {"text":""},{"bounds":{"x":350,"y":10,"w":200,"h":40}},
])
def test_fake_fixes_rejected(changed):
    ok,_=preserve_visible_text(snapshot(),snapshot(**changed),390)
    assert not ok

def test_genuine_expand_allowed():
    ok,_=preserve_visible_text(snapshot(),snapshot(bounds={"x":10,"y":10,"w":200,"h":80}),390)
    assert ok

def test_masking_properties_are_disallowed():
    css=safe_declarations({"display":"none","overflow":"hidden","overflow-x":"auto",
                           "font-size":"1px","height":"auto"})
    assert css=={"height":"auto"}
    assert safe_attributes({"lang":"hi"},"wrong-lang")=={"lang":"hi"}
    assert safe_attributes({"lang":"hi"},"possible-clipping")=={}
