from aksharacheck.detectors import indic_share,malformed_clusters,run_dom_detectors
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
