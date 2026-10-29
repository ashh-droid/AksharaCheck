"""Generate reader-first JSON, Markdown and standalone HTML audit reports.

The standalone HTML requires no JS build and never downloads fonts or scripts
from a third party. Data supplied by scanned sites is HTML-escaped.
"""
from __future__ import annotations

import html
import json
import struct
from collections import Counter
from pathlib import Path

FINDING_COPY={
    "broken-cluster":(
        "Broken character sequence",
        "A dependent sign has no valid letter before it. Browsers may show a dotted circle.",
        "Correct the affected text in the source. CSS cannot repair a mistyped Unicode sequence."
    ),
    "possible-clipping":(
        "Text may be cut off",
        "The browser measured more text height than the visible element allows. This is an indicator, not visual proof.",
        "Inspect the element on the original page. Hidden navigation or intentional animation may explain the measurement."
    ),
    "mobile-overflow":(
        "Text extends past its container",
        "A line is wider than its available space at the phone viewport.",
        "Inspect at phone width and allow appropriate line breaks without hiding text."
    ),
    "wrong-lang":(
        "Language tag may be wrong",
        "The script in this element does not match its inherited language tag.",
        "Set the appropriate language attribute, or label each language separately in mixed content."
    ),
    "mixed-language":(
        "Mixed scripts need language labels",
        "This text combines scripts whose pronunciation rules differ.",
        "Wrap each language span in the matching language attribute."
    ),
    "font-load-failed":(
        "Web font request failed",
        "The browser could not load a font resource requested by the page.",
        "Check the font URL and whether the failing font actually appears in visible text."
    ),
    "font-fallback":(
        "Another font was rendered",
        "Chromium used a different font from the first requested family.",
        "Check glyph appearance before treating this as a defect. Font fallback can be intentional."
    ),
    "legacy-font":(
        "Possible legacy encoded text",
        "The page may be using an older non-Unicode font encoding.",
        "Review the original text and font mapping before proposing a Unicode conversion."
    ),
    "tight-line-height":(
        "Line spacing is compact",
        "Multiple lines may have limited space for Indic marks.",
        "Review the appearance at normal zoom. This is an observation, not proof of clipping."
    ),
}
SECTIONS=(
    ("error","Characters or resources needing attention","Measured problems that deserve inspection."),
    ("warning","Potential rendering issues","These signals require visual confirmation before editing a page."),
    ("info","Additional observations","Useful context. These entries are not confirmed rendering defects."),
)
PNG_MAGIC=b"\x89PNG\r\n\x1a\n"


def esc(value):
    return html.escape(str(value if value is not None else ""),quote=True)


def _png_size(path: Path):
    """Read PNG dimensions without a third-party image dependency."""
    try:
        with path.open("rb") as inp:
            header=inp.read(24)
        if len(header)>=24 and header[:8]==PNG_MAGIC and header[12:16]==b"IHDR":
            return struct.unpack(">II",header[16:24])
    except OSError:
        pass
    return (0,0)


def _asset(name,folder):
    """Never turn scanned site text into an arbitrary file or URL link."""
    if not isinstance(name,str) or not name.endswith(".png"):
        return ""
    if Path(name).name!=name or not name.startswith(("element-","page-")):
        return ""
    return name if (folder/name).is_file() else ""


def _viewport(finding):
    widths=sorted(set(finding.get("viewports") or [finding.get("viewport",390)]))
    types=["Phone" if w<=430 else "Tablet" if w<=1024 else "Desktop" for w in widths]
    return " + ".join(dict.fromkeys(types))


def _evidence_summary(finding):
    kind=finding.get("detector","")
    d=finding.get("evidence") or {}
    if kind=="possible-clipping":
        hidden=d.get("overflow_pixels")
        if hidden is None:
            hidden=round(float(d.get("scroll_height",0))-float(d.get("client_height",0)),1)
        return "Measured content exceeds the visible area by "+esc(hidden)+" px."
    if kind=="mobile-overflow":
        extra=round(float(d.get("scroll_width",0))-float(d.get("client_width",0)),1)
        return "Text exceeds the available width by "+esc(extra)+" px."
    if kind=="wrong-lang":
        return "Page language: "+esc(d.get("effective","not provided"))+". Detected script: "+esc(d.get("script","Indic"))+"."
    if kind=="font-load-failed":
        code=d.get("status","request failed")
        return "Font request returned "+esc(code)+"."
    if kind=="font-fallback":
        return "Requested font: "+esc(d.get("requested","not provided"))+"."
    if kind=="broken-cluster":
        sequences=d.get("invalid_sequences") or []
        return str(len(sequences))+" malformed sign sequence(s) found in this element."
    return FINDING_COPY.get(kind,("","",""))[1]


def _photo(finding,folder):
    crop=_asset(finding.get("element_screenshot"),folder)
    shot=_asset(finding.get("screenshot"),folder)
    if crop:
        width,height=_png_size(folder/crop)
        if width>=40 and height>=40:
            return ('<a class="evidence-photo" href="'+esc(crop)+'" target="_blank" rel="noopener noreferrer">'
                    '<img src="'+esc(crop)+'" alt="Captured text from the browser" loading="lazy">'
                    '<span>Enlarge capture <span aria-hidden="true">↗</span></span></a>')
    if shot:
        return '<a class="screenshot-link" href="'+esc(shot)+'" target="_blank" rel="noopener noreferrer">Open browser screenshot <span aria-hidden="true">↗</span></a>'
    return ""


def _fix_message(finding):
    fix=finding.get("fix") or {}
    state=fix.get("status")
    if state=="verified":
        return '<span class="repair verified">✓ Independently verified in Chromium</span>'
    if state=="unverified":
        return '<span class="repair caution">Suggested repair did not pass verification</span>'
    if state=="not-applicable":
        return '<span class="repair neutral">Manual correction required</span>'
    if state=="unavailable":
        return '<span class="repair neutral">AI suggestion unavailable</span>'
    return ""



def _label(value, singular, plural=None):
    return str(value)+" "+(singular if value==1 else (plural or singular+"s"))


def _safe_target(url):
    from urllib.parse import urlsplit
    url=str(url or "")
    parsed=urlsplit(url)
    if parsed.scheme in {"http","https"} and parsed.hostname:
        return '<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(url)+'</a>'
    return esc(url)


def _observed(f):
    """Short, detector-specific measurement. Do not repeat the category's prose."""
    details=f.get("evidence") or {}
    kind=f.get("detector")
    if kind=="possible-clipping":
        amount=details.get("overflow_pixels")
        if amount is None:
            amount=max(0,float(details.get("scroll_height") or 0)-float(details.get("client_height") or 0))
        return "Content height exceeds the visible area by "+str(round(float(amount),1))+" px."
    if kind=="mobile-overflow":
        amount=max(0,float(details.get("scroll_width") or 0)-float(details.get("client_width") or 0))
        return "Text extends "+str(round(amount,1))+" px beyond its container."
    if kind=="tight-line-height":
        return "Measured line-height ratio: "+str(details.get("ratio","not available"))+"."
    if kind=="font-fallback":
        return "Requested font: "+str(details.get("requested","not available"))+"."
    if kind=="font-load-failed":
        return "Font request: HTTP "+str(details["status"])+"." if "status" in details else "Browser font request failed."
    if kind=="wrong-lang":
        return "Declared language: "+str(details.get("effective","not set"))+". Script: "+str(details.get("script","Indic"))+"."
    if kind=="broken-cluster":
        return _label(len(details.get("invalid_sequences") or []),"invalid character sequence")+"."
    if kind=="mixed-language":
        return "More than one Indic script appears within this element."
    if kind=="legacy-font":
        return "Computed font: "+str(details.get("computed_font","not available"))+"."
    return "Browser evidence is available for review."


def _fix_status(f):
    state=(f.get("fix") or {}).get("status")
    if state=="verified":
        return '<span class="result verified">Verified after a separate browser check</span>'
    if state=="unverified":
        return '<span class="result failed">Proposed repair failed verification</span>'
    if state=="not-applicable":
        return '<span class="result neutral">Manual correction needed</span>'
    if state=="unavailable":
        return '<span class="result neutral">AI generation unavailable</span>'
    return ""


def _finding_row(f, folder, index):
    detector=f.get("detector","")
    title,why,action=FINDING_COPY.get(detector,("Rendering observation","Inspect this occurrence.","Review the underlying page."))
    sample=str(f.get("sample") or "").strip()
    if len(sample)>180:
        sample=sample[:177]+"…"
    sample_html='<div class="sample" lang="und" dir="auto">'+esc(sample)+'</div>' if sample else ""
    note=esc(_observed(f))
    current=f.get("fix") or {}
    fix_code={**(current.get("css") or {}),**(current.get("attributes") or {})}
    fix_html=('<div class="fix-snippet"><strong>Proposed change</strong><pre>'+esc("\n".join(str(k)+": "+str(v)+";" for k,v in fix_code.items()))+'</pre></div>') if fix_code else ""
    photo=_photo(f,folder)
    # Images are shown inside expanded details only. A missing or 1px crop
    # must never create a huge empty rectangle on the main report.
    evidence=esc(json.dumps(f.get("evidence") or {},ensure_ascii=False,indent=2))
    widths=", ".join(str(w) for w in sorted(set(f.get("viewports") or [f.get("viewport",390)])))
    target=esc(f.get("url",""))
    selector=esc(f.get("selector",""))
    technical=(
        '<details class="technical"><summary>View evidence and next step</summary>'
        '<div class="technical-body"><p class="next-step"><strong>Recommended next step</strong><span>'+esc(action)+'</span></p>'
        +(('<p><strong>AI explanation</strong><span>'+esc(f["ai_explanation"])+'</span></p>') if f.get("ai_explanation") else "")
        +('<p class="technical-line"><strong>Page</strong><span>'+target+'</span></p>')
        +('<p class="technical-line"><strong>Element</strong><code>'+selector+'</code></p>')
        +('<p class="technical-line"><strong>Viewport widths</strong><span>'+esc(widths)+' px</span></p>')
        +(('<div class="capture"><strong>Browser capture</strong>'+photo+'</div>') if photo else "")
        +fix_html+'<div class="raw-evidence"><strong>Raw browser measurements</strong><pre>'+evidence+'</pre></div>'
        +'</div></details>')
    confidence='<span class="uncertain">Needs visual confirmation</span>' if f.get("confidence")=="suspected" else ""
    return ('<article class="finding-row" id="finding-'+esc(f.get("id",index))+'">'
            '<div class="finding-number">'+str(index).zfill(2)+'</div>'
            '<div class="finding-text"><div class="finding-top">'
            '<span class="viewport">'+esc(_viewport(f))+'</span>'+confidence+'</div>'
            +sample_html+'<div class="measurement">'+note+'</div>'
            +_fix_status(f)+technical+'</div></article>')


def _group(detector, findings, folder, severity):
    title,description,_=FINDING_COPY.get(detector,("Rendering observation","Measurements available for review.","Inspect this finding."))
    # One explanation per detector, instead of identical paragraphs on every finding.
    total=len(findings)
    preview=esc(next((f.get("sample") for f in findings if f.get("sample")),""))
    open_attr=" open" if severity!="info" else ""
    rows="".join(_finding_row(f,folder,i) for i,f in enumerate(findings,1))
    label="Potential" if severity=="warning" else ("Observation" if severity=="info" else "Error")
    return ('<details class="issue-group '+esc(severity)+'"'+open_attr+'>'
            '<summary class="group-summary"><span class="group-accent"></span>'
            '<span class="group-heading"><span class="group-category">'+esc(label)+'</span>'
            '<strong>'+esc(title)+'</strong><small>'+esc(description)+'</small></span>'
            '<span class="group-count">'+_label(total,"occurrence")+'</span>'
            '<span class="chevron" aria-hidden="true"></span></summary>'
            '<div class="group-items">'+rows+'</div></details>')


def _html_report(data,folder):
    from collections import defaultdict
    counts=Counter(f.get("severity","info") for f in data.get("findings",[]))
    target=data.get("target","")
    groups=defaultdict(list)
    for f in data.get("findings",[]):
        groups[(f.get("severity","info"),f.get("detector","unknown"))].append(f)
    priority={"error":0,"warning":1,"info":2}
    parts=[]
    for (severity,detector),findings in sorted(groups.items(),key=lambda pair:(priority.get(pair[0][0],3),-len(pair[1]),pair[0][1])):
        parts.append(_group(detector,findings,folder,severity))
    content="\n".join(parts) or (
        '<div class="empty"><span class="empty-icon" aria-hidden="true">✓</span>'
        '<h2>No issues detected by these checks</h2><p>This does not guarantee complete rendering correctness.</p></div>'
    )
    notices=[]
    if data.get("demo_mode"):
        notices.append('<div class="notice danger"><strong>Offline development demo</strong> No BharatCode model call was made. Sample repairs are predefined rules.</div>')
    if any("error" in page for page in data.get("pages",[])):
        notices.append('<div class="notice danger"><strong>Incomplete scan</strong> Some pages or viewports could not be checked. Missing data is not clean data.</div>')
    if not data.get("engine_version"):
        notices.append('<div class="notice subtle"><strong>Earlier scan data.</strong> This report has the latest design, but the recorded findings use an earlier scanner. Run a fresh scan to apply the latest detection rules.</div>')
    logo=(
        '<svg class="logo" viewBox="0 0 120 120" aria-hidden="true">'
        '<path d="M49.65 21.36 A40 40 0 1 1 49.65 98.64" fill="none" stroke="#0E6B4E" stroke-width="13" stroke-linecap="round"/>'
        '<g fill="#D9475A"><circle cx="34.83" cy="91.08" r="6.5"/>'
        '<circle cx="24.05" cy="77.54" r="6.5"/><circle cx="20" cy="60" r="6.5"/>'
        '<circle cx="24.05" cy="42.46" r="6.5"/><circle cx="34.83" cy="28.92" r="6.5"/></g></svg>'
    )
    css=r"""
@import url('https://fonts.googleapis.com/css2?family=Anek:wght@400;500;600;700;800&family=Anek+Devanagari:wght@400;500;600;700&family=Anek+Kannada:wght@400;500;600;700&display=swap');
:root{--paper:#F8FAF7;--ink:#1B2440;--muted:#56627A;--navy:#141B30;--line:#D8E4F0;--green:#0E6B4E;--red:#B8323F;--pale:#EAF5EF;--font:'Anek','Anek Devanagari','Anek Kannada','Nirmala UI',system-ui,sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--font);-webkit-font-smoothing:antialiased}
a{color:inherit}button,summary{font:inherit}a:focus-visible,summary:focus-visible{outline:3px solid var(--green);outline-offset:4px}
.shell{max-width:1140px;margin:0 auto;padding:0 clamp(18px,3vw,38px)}
.topbar{background:#fff;border-bottom:1px solid var(--line)}.topbar-inner{min-height:80px;display:flex;justify-content:space-between;align-items:center;gap:20px}
.brand{display:flex;align-items:center;gap:12px;min-width:0}.logo{width:40px;height:40px;flex:none}
.brand-name{font-size:25px;font-weight:800;letter-spacing:-.025em;line-height:1.05}
.brand-sub{display:flex;gap:10px;font-size:12px;color:var(--muted);margin-top:3px;line-height:1.2}
.top-actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap;justify-content:flex-end}
.top-actions a{font-size:13px;font-weight:650;text-decoration:none;padding:9px 13px;border:1px solid var(--line);border-radius:6px;color:var(--ink);background:#fff}
.top-actions a:hover{border-color:var(--green);color:var(--green)}
.hero{background:var(--paper);border-bottom:1px solid var(--line);position:relative;overflow:hidden}
.hero:before{position:absolute;content:"";top:0;bottom:0;left:max(16px,calc((100vw - 1070px)/2));width:1.5px;background:#EC97A5;opacity:.65;pointer-events:none}
.hero:after{content:"";position:absolute;inset:0;background-image:repeating-linear-gradient(to bottom,transparent 0,transparent 44px,rgba(184,204,230,.26) 45px,transparent 46px);pointer-events:none}
.hero-content{position:relative;z-index:1;padding-top:34px;padding-bottom:34px;padding-left:39px;display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:35px;align-items:center}
.kicker{font-size:12px;color:var(--green);font-weight:750;letter-spacing:.04em;margin:0 0 8px}
.hero h1{font-size:clamp(31px,3.65vw,46px);letter-spacing:-.035em;line-height:1.12;margin:0 0 11px;font-weight:800}
.subtitle{color:var(--muted);font-size:15px;line-height:1.55;margin:0;max-width:600px}
.scanned-url{display:block;font-size:13px;font-weight:650;margin-top:14px;color:var(--green);overflow-wrap:anywhere;text-underline-offset:3px}
.score{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:#fff;border:1px solid var(--line);border-radius:9px;padding:17px 10px;box-shadow:0 6px 16px #1B244006}
.score-item{text-align:center;padding:2px 7px;border-right:1px solid var(--line)}.score-item:last-child{border-right:0}
.score-num{font-size:29px;font-weight:800;line-height:1.15;font-variant-numeric:tabular-nums}
.score-num.error{color:var(--red)}.score-num.warning{color:#925516}.score-num.info{color:var(--green)}
.score-label{display:block;font-size:11px;font-weight:700;color:var(--muted);margin-top:4px}
.main{padding-top:30px;padding-bottom:55px}
.intro{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:22px}
.intro h2{font-size:23px;letter-spacing:-.025em;line-height:1.2;margin:0 0 5px;font-weight:800}
.intro p{color:var(--muted);font-size:14px;margin:0;max-width:670px}
.count-note{display:inline-flex;align-items:center;gap:9px;white-space:nowrap;font-size:12px;color:var(--green);font-weight:750;padding-top:4px}
.count-note:before{content:"";width:8px;height:8px;border-radius:50%;background:var(--green)}
.issue-group{margin:14px 0;background:#fff;border:1px solid var(--line);border-radius:10px;box-shadow:0 4px 15px rgba(27,36,64,.025);overflow:hidden}
.group-summary{display:flex;align-items:center;gap:17px;list-style:none;cursor:pointer;padding:18px 22px;min-height:100px}
.group-summary::-webkit-details-marker{display:none}.group-summary:hover{background:#FCFDFB}
.group-accent{width:3px;height:51px;border-radius:2px;flex:none;background:#F2AE5D}.issue-group.error .group-accent{background:#D9475A}.issue-group.info .group-accent{background:#87BFB1}
.group-heading{min-width:0;display:flex;flex-direction:column;flex:1;gap:1px}
.group-category{color:#975B13;font-weight:800;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
.issue-group.error .group-category{color:#B8323F}.issue-group.info .group-category{color:var(--green)}
.group-heading strong{font-size:18px;line-height:1.3;letter-spacing:-.015em}
.group-heading small{font-size:13px;color:var(--muted);line-height:1.45;max-width:750px;font-weight:400}
.group-count{font-size:12px;white-space:nowrap;color:var(--muted);font-weight:650}
.chevron{display:inline-flex;align-items:center;justify-content:center;flex:none;width:30px;height:30px;border:1px solid var(--line);border-radius:50%;background:#fff}
.chevron:after{content:"";width:7px;height:7px;border-right:2px solid var(--green);border-bottom:2px solid var(--green);transform:translateY(-2px) rotate(45deg)}
.issue-group[open]>.group-summary .chevron:after{transform:translateY(2px) rotate(225deg)}
.group-items{border-top:1px solid var(--line);padding:0 22px}
.finding-row{display:grid;grid-template-columns:32px minmax(0,1fr);gap:12px;padding:16px 0;border-bottom:1px solid #E9EFF4}
.finding-row:last-child{border-bottom:0}
.finding-number{color:#8793A5;font-size:12px;font-weight:700;padding-top:3px;font-variant-numeric:tabular-nums}
.finding-top{display:flex;align-items:center;gap:10px;margin-bottom:5px;flex-wrap:wrap}
.viewport{font-size:12px;font-weight:750;color:var(--ink)}
.uncertain{font-size:11px;color:#946323;background:#FFF2DF;border-radius:4px;padding:1px 7px}
.sample{font-size:clamp(16px,2.1vw,21px);line-height:1.6;font-weight:550;overflow-wrap:anywhere;color:var(--ink);margin:0 0 3px}
.measurement{font-size:13px;color:var(--muted);line-height:1.5}
.result{display:inline-block;margin:7px 0 0;border-radius:4px;padding:3px 8px;font-size:12px;font-weight:700}
.result.verified{color:var(--green);background:#E4F3E9}
.result.failed{color:var(--red);background:#FDEDEE}
.result.neutral{color:#526077;background:#F0F3F7}
.technical{margin:7px 0 0}
.technical summary{font-size:12px;cursor:pointer;color:var(--green);font-weight:750;width:fit-content}
.technical summary:hover{text-decoration:underline;text-underline-offset:3px}
.technical-body{margin-top:12px;padding:14px 18px;border:1px solid var(--line);border-radius:7px;background:#FAFCFE}
.technical-body p{margin:0 0 12px;font-size:13px;line-height:1.55}
.technical-body strong{display:block;color:var(--ink);font-size:12px;margin-bottom:3px}
.technical-line span{overflow-wrap:anywhere;color:var(--muted)}
.technical-line code{font-size:11px;overflow-wrap:anywhere;color:var(--muted)}
.technical-body pre{background:#F0F5F8;border:1px solid var(--line);padding:12px;font:12px/1.6 ui-monospace,SFMono-Regular,Consolas,monospace;overflow:auto;max-height:210px;white-space:pre-wrap;overflow-wrap:anywhere}
.capture{margin-bottom:12px;display:flex;align-items:flex-start;gap:10px;flex-wrap:wrap}
.capture .evidence-photo{width:min(100%,250px);border:1px solid var(--line);background:white;padding:6px;border-radius:5px;display:flex;flex-direction:column;gap:4px;text-decoration:none}
.capture .evidence-photo img{max-width:100%;max-height:150px;object-fit:contain;display:block}
.capture .evidence-photo span,.capture .screenshot-link{font-size:12px;font-weight:700;color:var(--green);text-decoration:underline}
.capture .screenshot-link{align-self:center}
.fix-snippet pre{border-left:3px solid var(--green)}
.raw-evidence{margin-top:12px}
.notice{margin:0 0 16px;padding:13px 16px;font-size:13px;background:#F1F5F7;border:1px solid var(--line);border-radius:6px;color:var(--muted)}
.notice strong{color:var(--ink)}.notice.danger{border-left:3px solid var(--red);background:#FFF3F3}
.notice.subtle{border-left:3px solid var(--green)}
.empty{padding:43px 24px;background:white;border:1px solid var(--line);text-align:center;border-radius:10px}
.empty-icon{display:inline-flex;background:#E9F5EF;color:var(--green);font-size:25px;width:45px;height:45px;align-items:center;justify-content:center;border-radius:50%}
.empty h2{font-size:23px;margin:14px 0 3px}.empty p{color:var(--muted);margin:0}
.footer{border-top:1px solid var(--line);padding:23px 0 35px;font-size:12px;color:var(--muted);display:flex;justify-content:space-between;gap:20px}
.footer span:last-child{white-space:nowrap}
@media(max-width:800px){.hero-content{grid-template-columns:minmax(0,1fr);gap:22px}.score{max-width:390px}.hero:before{left:24px}.hero-content{padding-left:41px}.topbar-inner{min-height:75px}}
@media(max-width:520px){.shell{padding:0 18px}.topbar-inner{min-height:74px;gap:10px}.brand{gap:8px}.logo{width:34px;height:34px}.brand-name{font-size:20px}.brand-sub{gap:5px;font-size:9px}.top-actions a{padding:7px 8px;font-size:11px}.hero-content{padding-left:29px;padding-top:26px;padding-bottom:27px}.hero:before{left:19px}.hero h1{font-size:31px}.score{padding:12px 7px}.score-num{font-size:25px}.main{padding-top:24px}.intro{display:block}.count-note{padding-top:12px}.group-summary{padding:14px 13px;gap:11px;min-height:0}.group-accent{height:55px}.group-heading strong{font-size:16px}.group-heading small{font-size:12px}.group-count{display:none}.group-items{padding:0 13px}.finding-row{grid-template-columns:22px minmax(0,1fr);gap:7px;padding:13px 0}.sample{font-size:18px}.technical-body{padding:12px}.footer{flex-wrap:wrap}}
@media(print){.topbar{border:0}.top-actions,.technical summary{display:none}.hero{background:#fff}.issue-group:not([open]) .group-items{display:block}.issue-group{break-inside:avoid}.group-summary{min-height:0}.main{padding-top:18px}}
"""
    # Use a local stylesheet in the standalone HTML, avoiding missing assets.
    target_html=_safe_target(target)
    score=(
        '<div class="score" role="group" aria-label="Finding counts">'
        '<div class="score-item"><span class="score-num error">'+str(counts["error"])+'</span><span class="score-label">Errors</span></div>'
        '<div class="score-item"><span class="score-num warning">'+str(counts["warning"])+'</span><span class="score-label">Warnings</span></div>'
        '<div class="score-item"><span class="score-num info">'+str(counts["info"])+'</span><span class="score-label">Notes</span></div></div>'
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        '<meta name="description" content="AksharaCheck browser evidence report for Indic text rendering.">'
        '<title>AksharaCheck | Rendering review</title><style>'+css+'</style></head>'
        '<body><header class="topbar"><div class="shell topbar-inner">'
        '<div class="brand">'+logo+'<div><div class="brand-name">AksharaCheck</div>'
        '<div class="brand-sub"><span lang="hi">अक्षर जाँच</span><span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span></div></div></div>'
        '<nav class="top-actions" aria-label="Report exports">'
        '<a href="report.json">JSON</a><a href="report.md">Markdown</a></nav></div></header>'
        '<section class="hero"><div class="shell hero-content"><div>'
        '<p class="kicker">BROWSER RENDERING REVIEW</p>'
        '<h1>Every letter matters.</h1>'
        '<p class="subtitle">A focused look at the issues Chromium detected. Warnings are candidates for review, not confirmed faults.</p>'
        '<div class="scanned-url">'+target_html+'</div></div>'+score+'</div></section>'
        '<main class="shell main">'+''.join(notices)
        +'<div class="intro"><div><h2>Findings worth reviewing</h2><p>Grouped by issue type, with the measurements and browser captures one click away.</p></div>'
        +'<div class="count-note">'+_label(len(data.get("findings",[])),"finding")+' recorded</div></div>'
        +content+'</main><footer class="shell footer"><span>AksharaCheck. Browser measurements, not a full accessibility audit.</span>'
        '<span>Checked with Chromium</span></footer></body></html>'
    )


def write_reports(data,dest):
    folder=Path(dest)
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"report.json").write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    counts=Counter(f.get("severity","info") for f in data.get("findings",[]))
    lines=["# AksharaCheck browser review","", "Target: "+str(data.get("target","")),
           "Findings: "+str(counts["error"])+" errors, "+str(counts["warning"])+" warnings, "+
           str(counts["info"])+" informational.",""]
    if data.get("demo_mode"):
        lines.extend(["Offline development demo. No BharatCode model was called.",""])
    for f in data.get("findings",[]):
        lines.extend(["## "+str(f.get("severity","info")).upper()+": "+
                      FINDING_COPY.get(f.get("detector"),("Observation",))[0],
                      "",str(f.get("sample","")), "",
                      "Page: "+str(f.get("url","")),
                      "Element: "+str(f.get("selector","")),
                      "Browser evidence: "+json.dumps(f.get("evidence") or {},ensure_ascii=False),
                      "Repair state: "+str((f.get("fix") or {}).get("status","not requested")),""])
    (folder/"report.md").write_text("\n".join(lines),encoding="utf-8")
    (folder/"report.html").write_text(_html_report(data,folder),encoding="utf-8")
