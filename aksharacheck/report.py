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


def _card(finding,folder,index):
    kind=str(finding.get("detector",""))
    title,why,action=FINDING_COPY.get(kind,("Rendering observation","Review the browser measurements.","Inspect the relevant element."))
    severity=finding.get("severity","info")
    confidence="Suspected, review needed" if finding.get("confidence")=="suspected" else "Browser measurement"
    sample=str(finding.get("sample","")).strip()
    preview='<p class="sample" dir="auto">'+esc(sample)+'</p>' if sample else ""
    photo=_photo(finding,folder)
    status=_fix_message(finding)
    target=esc(finding.get("url",""))
    selector=esc(finding.get("selector",""))
    raw=esc(json.dumps(finding.get("evidence") or {},indent=2,ensure_ascii=False))
    patch=finding.get("fix") or {}
    declarations={**(patch.get("css") or {}),**(patch.get("attributes") or {})}
    patch_view=('<pre class="patch">'+esc("\n".join(str(k)+": "+str(v)+";" for k,v in declarations.items()))+'</pre>') if declarations else ""
    details=(
        '<details class="technical"><summary>Inspect details and suggested next step</summary>'
        '<div class="details-body"><p><strong>Next step:</strong> '+esc(action)+'</p>'
        '<p class="meta"><strong>Page:</strong> '+target+'</p>'
        '<p class="meta"><strong>Element:</strong> <code>'+selector+'</code></p>'
        '<p class="meta"><strong>Observed width:</strong> '+esc(str(finding.get("viewports") or [finding.get("viewport")]))+' px</p>'
        '<pre>'+raw+'</pre>'+patch_view+'</div></details>'
    )
    return (
        '<article class="issue"><div class="issue-main">'
        '<span class="severity '+esc(severity)+'">'+esc(severity)+'</span>'
        '<div class="issue-copy"><div class="issue-heading"><h3>'+esc(title)+'</h3>'
        '<span class="scope">'+esc(_viewport(finding))+'</span></div>'
        +preview+
        '<p class="observation">'+_evidence_summary(finding)+'</p>'
        '<p class="why">'+esc(why)+'</p>'
        '<div class="issue-tags"><span class="confidence">'+esc(confidence)+'</span>'+status+'</div></div>'
        +photo+'</div>'+details+'</article>'
    )


def _html_report(data,folder):
    counts=Counter(f.get("severity","info") for f in data.get("findings",[]))
    target=esc(data.get("target",""))
    target_link='<a href="'+target+'" target="_blank" rel="noopener noreferrer">'+target+'</a>'
    cards=[]
    for severity,title,desc in SECTIONS:
        findings=[f for f in data.get("findings",[]) if f.get("severity")==severity]
        if not findings:
            continue
        cards.append('<section class="finding-section" id="section-'+severity+'">'
                     '<div class="section-heading"><div><h2>'+esc(title)+'</h2><p>'+esc(desc)+'</p></div>'
                     '<span class="section-count">'+str(len(findings))+'</span></div>'
                     +"\n".join(_card(f,folder,i) for i,f in enumerate(findings))+'</section>')
    body="\n".join(cards) if cards else '<div class="empty-state"><strong>No issues detected by the implemented checks.</strong><p>This does not guarantee that all characters render correctly.</p></div>'
    if data.get("demo_mode"):
        body='<aside class="demo-banner"><strong>Offline engineering demonstration.</strong> No BharatCode API was called. Example repairs are predefined local rules.</aside>'+body
    if any("error" in page for page in data.get("pages",[])):
        body='<aside class="demo-banner"><strong>Partial scan.</strong> One or more page widths could not be checked. Missing results are not counted as clean.</aside>'+body
    links=' '.join('<a href="#section-'+severity+'">'+esc(title)+'</a>' for severity,title,_ in SECTIONS if counts[severity])
    warning_note=(
        "Potential issues are screening signals, not confirmed visual defects. "
        "The scanner does not change the audited website."
    )
    svg=('<svg class="mark" aria-hidden="true" viewBox="0 0 120 120">'
         '<path d="M49.65 21.36 A40 40 0 1 1 49.65 98.64" fill="none" stroke="#55C59D" stroke-width="13" stroke-linecap="round"/>'
         '<g fill="#F27D92"><circle cx="34.83" cy="91.08" r="6.5"/><circle cx="24.05" cy="77.54" r="6.5"/>'
         '<circle cx="20" cy="60" r="6.5"/><circle cx="24.05" cy="42.46" r="6.5"/>'
         '<circle cx="34.83" cy="28.92" r="6.5"/></g></svg>')
    css=r"""
:root{--paper:#F8FAF7;--ink:#1B2440;--muted:#505E76;--line:#DCE5EB;--rule:#B8CCE6;--green:#0E6B4E;--red:#B8323F;--navy:#141B30;font-family:system-ui,"Noto Sans Devanagari","Noto Sans Kannada",sans-serif;color:var(--ink);background:var(--paper)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;line-height:1.58}
a{color:inherit}a:focus-visible,summary:focus-visible{outline:3px solid var(--green);outline-offset:4px}
.container{max-width:1160px;padding:0 28px;margin:auto}
.masthead{background:var(--navy);color:white}
.masthead-inner{padding-top:30px;padding-bottom:35px}
.brand{display:flex;align-items:center;gap:14px}.mark{width:45px;height:45px;flex-shrink:0}
.brand-name{font-size:27px;font-weight:750;letter-spacing:-.03em}
.masthead-bottom{display:flex;justify-content:space-between;align-items:flex-end;gap:20px;margin-top:27px}
.kicker{font-size:11px;letter-spacing:.13em;color:#BCE9D5;text-transform:uppercase;font-weight:700}
.masthead h1{font-size:clamp(29px,4vw,43px);line-height:1.12;letter-spacing:-.035em;margin:7px 0 4px}
.target{color:#CBD9E8;font-size:13px;overflow-wrap:anywhere}.target a{text-underline-offset:3px}
.actions{display:flex;gap:9px;flex-wrap:wrap}
.actions a{font-size:13px;font-weight:600;text-decoration:none;border:1px solid #5E6D83;border-radius:5px;padding:9px 12px;white-space:nowrap}
.actions a:hover{background:#26334B}
.summary-wrap{background:var(--paper);background-image:repeating-linear-gradient(to bottom,transparent 0,transparent 47px,rgba(184,204,230,.18) 48px,transparent 49px);border-bottom:1px solid var(--line)}
.summary{padding:25px 0 27px}
.stat-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.stat{background:white;border:1px solid var(--line);border-radius:8px;padding:16px 19px;display:flex;align-items:center;gap:16px;min-height:82px}
.stat-number{font-size:35px;line-height:1;font-weight:760;min-width:32px;font-variant-numeric:tabular-nums}
.stat.error .stat-number{color:var(--red)}.stat.warning .stat-number{color:#915C10}.stat.info .stat-number{color:var(--green)}
.stat-label{font-weight:700;font-size:14px}.stat-note{font-size:12px;color:var(--muted);margin-top:2px}
.notice{font-size:13px;color:var(--muted);margin:15px 0 0;max-width:90ch}
.contents{display:flex;flex-wrap:wrap;align-items:center;gap:16px;margin:22px 0 0}
.contents a{font-size:13px;color:var(--green);font-weight:700;text-decoration:none;border-bottom:1px solid #8FBFAE}
main{padding:36px 0 65px}.finding-section{margin-bottom:37px}
.section-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:0 0 15px}
.section-heading h2{margin:0;font-size:23px;letter-spacing:-.025em;line-height:1.2}
.section-heading p{color:var(--muted);font-size:13px;margin:5px 0 0}
.section-count{display:inline-flex;align-items:center;justify-content:center;width:37px;height:37px;border:1px solid var(--line);border-radius:50%;font-size:14px;font-weight:700;color:var(--muted);background:#fff;flex-shrink:0}
.issue{border:1px solid var(--line);background:white;border-radius:9px;margin:10px 0;box-shadow:0 3px 14px rgba(27,36,64,.025);overflow:hidden}
.issue-main{display:flex;align-items:flex-start;gap:17px;padding:19px 21px}
.severity{font-size:11px;line-height:1.4;letter-spacing:.02em;text-transform:capitalize;font-weight:700;border-radius:4px;padding:5px 9px;flex:none}
.severity.error{background:#FCE8E9;color:var(--red)}.severity.warning{background:#FFF1DC;color:#825010}.severity.info{background:#E8F2F0;color:#0E6B4E}
.issue-copy{flex:1;min-width:0}
.issue-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.issue h3{font-size:17px;letter-spacing:-.015em;line-height:1.35;margin:1px 0 0}
.scope{color:#5C6A80;font-size:12px;white-space:nowrap;flex-shrink:0}
.sample{font-size:clamp(18px,2vw,24px);font-weight:500;line-height:1.5;margin:7px 0 10px;overflow-wrap:anywhere}
.observation{color:var(--ink);font-size:13px;font-weight:600;margin:9px 0 3px}
.why{font-size:13px;color:var(--muted);margin:0;max-width:77ch}
.issue-tags{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}
.confidence,.repair{font-size:11px;border-radius:4px;padding:3px 7px;background:#F3F6F8;color:#607088;font-weight:650}
.repair.verified{color:var(--green);background:#E6F3EC}
.repair.caution{color:var(--red);background:#FCE8E9}
.repair.neutral{color:#596680;background:#F2F4F7}
.evidence-photo{display:flex;flex-direction:column;flex:0 0 164px;max-width:164px;align-items:center;gap:5px;text-decoration:none;border:1px solid var(--line);border-radius:5px;background:var(--paper);padding:7px}
.evidence-photo img{width:100%;max-height:92px;object-fit:contain}
.evidence-photo span,.screenshot-link{font-size:11px;color:var(--green);font-weight:650}
.screenshot-link{display:inline-block;flex:0 0 105px;max-width:105px;text-decoration:none;border-left:1px solid var(--line);padding-left:13px;line-height:1.4;margin-top:5px}
.technical{border-top:1px solid var(--line);padding:0 21px}
.technical summary{font-weight:650;font-size:12px;color:var(--green);cursor:pointer;padding:10px 0;list-style:revert}
.details-body{border-top:1px dashed var(--line);padding:14px 0 18px;font-size:13px}
.details-body p{margin:0 0 9px}.meta{color:var(--muted);overflow-wrap:anywhere}
pre{background:#F3F6F8;border:1px solid var(--line);border-radius:6px;padding:13px;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere;overflow-x:auto;max-height:300px}
code{font-size:12px;overflow-wrap:anywhere}.patch{border-left:3px solid var(--green);background:#EAF5EE}
.demo-banner{padding:15px 18px;background:#FCE8E9;border-left:4px solid var(--red);font-size:13px;margin:15px 0}
.empty-state{padding:35px;background:white;border:1px solid var(--line);border-radius:9px}
.empty-state p{color:var(--muted)}
.report-footer{border-top:1px solid var(--line);padding:20px 0 35px;color:var(--muted);font-size:12px}
@media(max-width:760px){.container{padding:0 18px}.masthead-inner{padding-top:24px;padding-bottom:28px}.masthead-bottom{align-items:flex-start;flex-direction:column;gap:18px}.stat-row{gap:8px}.stat{padding:13px;min-height:76px;gap:8px}.stat-number{font-size:27px}.stat-label{font-size:12px}.stat-note{font-size:11px}.issue-main{flex-wrap:wrap;padding:15px;gap:10px}.issue-copy{flex-basis:calc(100% - 91px)}.evidence-photo{margin-left:82px;max-width:170px;flex-basis:170px}.screenshot-link{flex:1;margin-left:82px}.technical{padding:0 15px}.scope{white-space:normal}.section-heading h2{font-size:21px}}
@media(max-width:420px){.stat-row{grid-template-columns:1fr 1fr 1fr;gap:6px}.stat{flex-direction:column;text-align:center;align-items:center;padding:12px 5px;gap:4px;min-height:91px}.stat-number{font-size:27px}.stat-note{line-height:1.2}.issue-heading{flex-direction:column;gap:2px}.issue-copy{flex-basis:calc(100% - 83px)}.sample{font-size:19px}.evidence-photo,.screenshot-link{margin-left:72px}}
@media print{.masthead{background:#141B30!important;print-color-adjust:exact}.issue{break-inside:avoid}.technical{display:none}a{text-decoration:none}}
"""
    page=(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light">'
        '<title>AksharaCheck | Browser evidence review</title><style>'+css+'</style></head>'
        '<body><header class="masthead"><div class="container masthead-inner">'
        '<div class="brand">'+svg+'<span class="brand-name">AksharaCheck</span></div>'
        '<div class="masthead-bottom"><div><div class="kicker">Rendering review</div>'
        '<h1>What the browser found.</h1><p class="target">'+target_link+'</p></div>'
        '<div class="actions"><a href="report.json">JSON report</a><a href="report.md">Markdown</a></div>'
        '</div></div></header>'
        '<section class="summary-wrap"><div class="container summary">'
        '<div class="stat-row">'
        '<div class="stat error"><span class="stat-number">'+str(counts["error"])+'</span><div><div class="stat-label">Errors</div><div class="stat-note">Review first</div></div></div>'
        '<div class="stat warning"><span class="stat-number">'+str(counts["warning"])+'</span><div><div class="stat-label">Warnings</div><div class="stat-note">Needs inspection</div></div></div>'
        '<div class="stat info"><span class="stat-number">'+str(counts["info"])+'</span><div><div class="stat-label">Notes</div><div class="stat-note">Context only</div></div></div>'
        '</div><p class="notice">'+esc(warning_note)+'</p>'
        '<nav class="contents" aria-label="Report sections">'+links+'</nav></div></section>'
        '<main class="container">'+body+'</main>'
        '<footer class="report-footer"><div class="container">AksharaCheck · Chromium measurements, not a guarantee of exhaustive rendering correctness.</div></footer>'
        '</body></html>'
    )
    return page


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
