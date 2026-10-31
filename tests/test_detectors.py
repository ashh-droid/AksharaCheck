from aksharacheck.detectors import indic_share,malformed_clusters,run_dom_detectors,font_mismatch_findings
from aksharacheck.ai import safe_declarations
from aksharacheck.security import validate_url,UnsafeURL
import pytest

def node(**updates):
    base={'selector':'[data-akshara-id="ak-1"]','text':'यह हिन्दी भाषा का उदाहरण है',
          'font':'sans-serif','lang':'hi','clientWidth':100,'scrollWidth':100,'clientHeight':100,
          'scrollHeight':100,'overflowX':'visible','overflowY':'visible','fontSize':20,
          'lineHeight':35,'lineCount':2,'intentionalClamp':False}
    return {**base,**updates}

def detectors(n,viewport=390):return run_dom_detectors('https://example.com',viewport,[n])

def test_detects_wrong_lang():assert any(f['detector']=='wrong-lang' for f in detectors(node(lang='en')))
def test_detects_overflow():assert any(f['detector']=='mobile-overflow' for f in detectors(node(scrollWidth=240)))
def test_overflow_opt_out():assert not any(f['detector']=='mobile-overflow' for f in detectors(node(scrollWidth=240,overflowX='auto')))
def test_detects_clipping():assert any(f['detector']=='possible-clipping' for f in detectors(node(clientHeight=25,scrollHeight=80,overflowY='hidden')))
def test_detects_line_height():assert any(f['detector']=='tight-line-height' for f in detectors(node(lineHeight=22)))
def test_detects_broken_cluster():assert malformed_clusters('काि')
def test_indic_script_share():assert indic_share('ಕನ್ನಡ','kn')==1.0

def test_css_blocks_data_exfiltration():
    assert safe_declarations({'background-image':'url(https://evil.com/x)','height':'20px','font-family':'url(http://evil)'})=={'height':'20px'}

def test_ssrf_blocks_localhost():
    with pytest.raises(UnsafeURL):validate_url('http://127.0.0.1:8000')
    assert validate_url('http://127.0.0.1:8000',allow_local=True)

def test_rejects_url_credentials():
    with pytest.raises(UnsafeURL):validate_url('http://user:pass@example.com')

def test_hidden_single_pixel_navigation_does_not_count_as_clipping():
    result=detectors(node(
        text="सामग्री पर जाएँ",
        fontSize=16,clientHeight=1,scrollHeight=63,
        clientWidth=200,overflowY="hidden",bounds={"x":10,"y":20,"w":200,"h":1}
    ))
    assert not any(f["detector"]=="possible-clipping" for f in result)


def test_trivial_ink_overhang_does_not_count_as_clipping():
    result=detectors(node(
        fontSize=18,clientHeight=28,scrollHeight=32,
        clientWidth=200,overflowY="hidden",bounds={"x":10,"y":20,"w":200,"h":28}
    ))
    assert not any(f["detector"]=="possible-clipping" for f in result)


def test_real_truncated_text_still_flagged():
    result=detectors(node(
        fontSize=24,clientHeight=18,scrollHeight=38,
        clientWidth=220,overflowY="hidden",bounds={"x":10,"y":20,"w":220,"h":18}
    ))
    assert any(f["detector"]=="possible-clipping" for f in result)


def test_hidden_offscreen_navigation_not_flagged():
    result=detectors(node(
        fontSize=16,clientHeight=24,scrollHeight=75,
        clientWidth=200,overflowY="hidden",offscreen=True,
        bounds={"x":-300,"y":20,"w":200,"h":24}
    ))
    assert not any(f["detector"]=="possible-clipping" for f in result)


@pytest.mark.parametrize("ratio", [1.2, 1.25, 1.3])
def test_normal_hindi_line_spacing_is_not_a_defect_note(ratio):
    # DD News on 31 Oct 2026 used 20/24 and 16/20 line-height, with
    # readable text and no demonstrated clipping in its browser screenshots.
    result=detectors(node(text="स्टैच्यू ऑफ यूनिटी के पास रेन फॉरेस्ट बना पर्यटन का नया आकर्षण",
                          fontSize=20,lineHeight=20*ratio,lineCount=2))
    assert not any(f["detector"]=="tight-line-height" for f in result)


def test_very_tight_multiline_indic_text_still_gets_review_note():
    result=detectors(node(text="यह हिन्दी भाषा का उदाहरण है",fontSize=20,lineHeight=18,lineCount=2))
    notes=[f for f in result if f["detector"]=="tight-line-height"]
    assert len(notes)==1 and notes[0]["severity"]=="info"


@pytest.mark.parametrize("word",["राष्ट्रीय","अंतरराष्ट्रीय"])
def test_expected_windows_arial_to_nirmala_glyph_fallback_is_not_an_error(word):
    observed=node(text=word,font="Arial",platform_fonts=[
        {"familyName":"Nirmala UI","postScriptName":"NirmalaUI-Bold","glyphCount":len(word),"isCustomFont":False}])
    assert font_mismatch_findings("https://ddnews.gov.in/",390,[observed])==[]


def test_unknown_indic_font_substitution_remains_visible_as_review_note():
    observed=node(text="राष्ट्रीय",font="Custom Hindi Typeface",platform_fonts=[
        {"familyName":"Nirmala UI","glyphCount":8,"isCustomFont":False}])
    notes=font_mismatch_findings("https://example.com/",390,[observed])
    assert len(notes)==1
    assert notes[0]["severity"]=="info"
    assert notes[0]["detector"]=="font-fallback"


def test_arbitrary_nonindic_arial_fallback_is_not_suppressed():
    observed=node(text="ಕನ್ನಡ ವಾರ್ತೆ",font="Arial",platform_fonts=[
        {"familyName":"Nirmala UI","glyphCount":7,"isCustomFont":False}])
    notes=font_mismatch_findings("https://example.com/",390,[observed])
    assert len(notes)==1
