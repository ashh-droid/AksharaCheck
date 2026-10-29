"""Generate JSON, Markdown and a standalone HTML report.

The HTML needs no JavaScript and no network: styles are inline and the Anek
fonts are copied next to the report. Everything that comes from a scanned
site is HTML-escaped.
"""
from __future__ import annotations

import html
import json
import shutil
import struct
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

# title, why it matters, what to do when no automatic repair applies
FINDING_COPY={
    "broken-cluster":(
        "Broken letters",
        "A vowel sign, nukta or virama has no letter to attach to, so browsers draw it on a dotted circle.",
        "Correct the text itself. This is a typing or conversion mistake, so CSS cannot repair it."
    ),
    "possible-clipping":(
        "Letters may be cut off",
        "The text is taller than the box that shows it, so marks above or below the line can disappear.",
        "Let the box grow with its text, for example with height: auto and a roomier line height."
    ),
    "mobile-overflow":(
        "Text runs off the screen on phones",
        "A line is wider than the space it has at phone width.",
        "Allow the line to wrap, without hiding or shrinking the text."
    ),
    "wrong-lang":(
        "Wrong language tag",
        "The text is in one script but tagged as another language, so screen readers use the wrong voice and browsers may pick the wrong font.",
        "Set the lang attribute that matches the text, such as lang=\"hi\" or lang=\"kn\"."
    ),
    "mixed-language":(
        "Two languages without labels",
        "Hindi and Kannada sit in one element with one language tag.",
        "Wrap each language in its own element with the matching lang attribute."
    ),
    "font-load-failed":(
        "Web font did not load",
        "The browser could not download a font the page asked for.",
        "Check the font address, and whether that font is actually used for visible text."
    ),
    "font-fallback":(
        "A different font was used",
        "Chromium drew this text with a font other than the first one the page asked for.",
        "Compare the letters with the intended font. A fallback can be deliberate."
    ),
    "legacy-font":(
        "Old non-Unicode font",
        "The text looks like Latin letters shown through a legacy Indic font, which search, copy and screen readers cannot read.",
        "Convert the text to Unicode and use a Unicode font."
    ),
    "tight-line-height":(
        "Tight line spacing",
        "Several lines sit close together, which leaves little room for Indic marks.",
        "Check it at normal zoom. A line height of about 1.6 suits Devanagari and Kannada."
    ),
}
# One vocabulary everywhere: Fix, Check, Note.
SEVERITY={"error":("Fix","To fix"),"warning":("Check","To check"),"info":("Note","Notes")}
ORDER=("error","warning","info")
PNG_MAGIC=b"\x89PNG\r\n\x1a\n"
ASSETS=Path(__file__).resolve().parent/"assets"
FONT_FILES=[f"font-anek-{script}-{weight}.woff2" for script in ("latin","devanagari","kannada") for weight in ("400","600")]


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


def _usable_crop(name,folder):
    """A crop worth showing: real pixels, not a 1 px sliver."""
    crop=_asset(name,folder)
    if not crop:
        return ""
    width,height=_png_size(folder/crop)
    return crop if width>=60 and height>=24 and width/height<=16 else ""


def _label(value, singular, plural=None):
    return f"{value:,} "+(singular if value==1 else (plural or singular+"s"))


def _lang_of(text):
    deva=sum(0x0900<=ord(c)<=0x097F for c in text)
    kan=sum(0x0C80<=ord(c)<=0x0CFF for c in text)
    if deva==kan==0:
        return "und"
    return "hi" if deva>=kan else "kn"


def _widths(finding):
    widths=sorted(set(finding.get("viewports") or [finding.get("viewport",390)]))
    names=[("phone" if w<=430 else "tablet" if w<=1024 else "desktop")+f" ({w} px)" for w in widths]
    return " and ".join(names)


def _where(finding):
    widths=sorted(set(finding.get("viewports") or [finding.get("viewport",390)]))
    kinds=list(dict.fromkeys("Phone" if w<=430 else "Tablet" if w<=1024 else "Desktop" for w in widths))
    return " and ".join([kinds[0]]+[k.lower() for k in kinds[1:]])


def _safe_link(url, text=None):
    url=str(url or "")
    try:
        parsed=urlsplit(url)
    except ValueError:
        return esc(text or url)
    if parsed.scheme in {"http","https"} and parsed.hostname:
        return '<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(text or url)+'</a>'
    return esc(text or url)


def _page_name(url):
    try:
        parts=urlsplit(str(url or ""))
    except ValueError:
        return str(url or "")
    if parts.scheme not in {"http","https"} or not parts.hostname:
        return str(url or "Scanned page")
    path=parts.path.rstrip("/")
    return (parts.netloc+path) or str(url)


def _when(value):
    value=str(value or "").strip()
    if not value:
        return ""
    try:
        moment=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:
        return value
    return f"{moment.day} {moment:%b %Y}, {moment:%H:%M} UTC"


def _observed(f):
    """Short, detector-specific measurement. Do not repeat the category's prose."""
    details=f.get("evidence") or {}
    kind=f.get("detector")
    if kind=="possible-clipping":
        amount=details.get("overflow_pixels")
        if amount is None:
            amount=max(0,float(details.get("scroll_height") or 0)-float(details.get("client_height") or 0))
        return f"The text needs {round(float(amount),1):g} px more height than the box gives it."
    if kind=="mobile-overflow":
        amount=max(0,float(details.get("scroll_width") or 0)-float(details.get("client_width") or 0))
        return f"The line runs {round(amount,1):g} px past its container."
    if kind=="tight-line-height":
        return "Line height is "+str(details.get("ratio","not measured"))+" times the font size."
    if kind=="font-fallback":
        return "The page asked for "+str(details.get("requested","another font"))+"."
    if kind=="font-load-failed":
        return "The font request returned HTTP "+str(details["status"])+"." if "status" in details else "The font request failed."
    if kind=="wrong-lang":
        return ("Tagged as "+str(details.get("effective") or "no language")+", written in "
                +str(details.get("script","an Indic script")).capitalize()+".")
    if kind=="broken-cluster":
        return ""
    if kind=="mixed-language":
        scripts=details.get("scripts") or {}
        parts=[f"{name.capitalize()} ({count} letters)" for name,count in scripts.items()]
        return "Scripts in one element: "+", ".join(parts)+"." if parts else "More than one script in one element."
    if kind=="legacy-font":
        return "Font used: "+str(details.get("computed_font","not recorded"))+"."
    return ""


def _sequences(f):
    """The exact characters of each broken letter, the evidence a developer can search for."""
    items=(f.get("evidence") or {}).get("invalid_sequences") or []
    if not items:
        return ""
    rows=[]
    for item in items[:6]:
        seq=str(item.get("sequence",""))
        mark=seq[-1:] if seq else ""
        codes=" ".join(esc(c) for c in item.get("codepoints") or [])
        # The sequence as typed: the browser draws its own dotted circle, which is the evidence.
        rows.append('<li><span class="glyph" lang="'+_lang_of(seq)+'">'+esc(seq.strip() or mark)+'</span>'
                    '<code>'+codes+'</code><span class="seq-why">'+esc(str(item.get("reason","")).capitalize())+'</span></li>')
    return '<ul class="sequences" aria-label="Characters">'+"".join(rows)+'</ul>'


def _css_text(change):
    return "\n".join(f"{k}: {v};" for k,v in (change.get("css") or {}).items())+(
        "\n".join(f'{k}="{v}"' for k,v in (change.get("attributes") or {}).items()))


def _explanation(f):
    english=str(f.get("ai_explanation") or "").strip()
    if not english:
        return ""
    lines=['<p>'+esc(english)+'</p>']
    for code,name in (("hi","हिंदी"),("kn","ಕನ್ನಡ")):
        text=str(f.get("summary_"+code) or "").strip()
        if text:
            lines.append('<p class="translation"><span class="lang-name" lang="'+code+'">'+name+'</span>'
                         '<span lang="'+code+'">'+esc(text)+'</span></p>')
    return '<div class="ai"><p class="ai-label">BharatCode explanation</p>'+"".join(lines)+'</div>'


def _attempts(fix):
    tries=fix.get("attempts") or []
    if len(tries)<2 and all(t.get("status")=="verified" for t in tries):
        return ""
    rows=[]
    for t in tries:
        ok=t.get("status")=="verified"
        rows.append('<li class="'+("ok" if ok else "bad")+'"><span class="mark" aria-hidden="true">'+("✓" if ok else "✗")+'</span>'
                    '<code>'+esc(_css_text(t).replace("\n"," "))+'</code>'
                    '<span>'+("Passed the browser check" if ok else "Rejected: "+esc(t.get("reason") or "did not pass"))+'</span></li>')
    return ('<div class="attempts"><p class="attempts-title">BharatCode suggested '+_label(len(tries),"repair")
            +', and Chromium tested each one</p><ol>'+"".join(rows)+'</ol></div>')


def _repair(f, folder, before):
    """What to do next: a verified fix with before and after, a failed one with the reason, or a manual step."""
    _,_,action=FINDING_COPY.get(f.get("detector"),("","","Review the element on the page."))
    fix=f.get("fix") or {}
    state=fix.get("status")
    if state=="verified":
        after=_usable_crop(fix.get("after_screenshot"),folder)
        width=fix.get("viewport") or f.get("viewport")
        compare=""
        if after and not before:
            compare=('<div class="compare single"><figure><img src="'+esc(after)+'" alt="The element after the fix">'
                     '<figcaption>After the fix</figcaption></figure></div>')
        if before and after:
            compare=('<div class="compare"><figure><img src="'+esc(before)+'" alt="The element before the fix">'
                     '<figcaption>Before</figcaption></figure><figure><img src="'+esc(after)+'" alt="The element after the fix">'
                     '<figcaption>After</figcaption></figure></div>')
        return ('<div class="repair ok"><p class="repair-title"><span aria-hidden="true">✓</span> Fix verified in a fresh Chromium at '
                +esc(width)+' px</p><pre>'+esc(_css_text(fix))+'</pre>'+compare+_attempts(fix)+'</div>')
    if state=="unverified":
        reason=fix.get("reason") or "it did not pass the browser check"
        return ('<div class="repair bad"><p class="repair-title"><span aria-hidden="true">✗</span> No suggested fix passed. '
                +esc(reason)+'.</p>'+_attempts(fix)+'<p class="next">'+esc(action)+'</p></div>')
    note=""
    if state=="unavailable":
        note='<p class="muted">BharatCode was not available for this scan.</p>'
    return '<div class="repair todo"><p class="repair-title">What to change</p><p>'+esc(action)+'</p>'+note+'</div>'


def _card(f, folder):
    severity=f.get("severity","info")
    word=SEVERITY.get(severity,SEVERITY["info"])[0]
    sample=str(f.get("sample") or "").strip()
    if len(sample)>220:
        sample=sample[:217]+"…"
    before=_usable_crop(f.get("element_screenshot"),folder)
    fix=f.get("fix") or {}
    compared=fix.get("status")=="verified" and _usable_crop(fix.get("after_screenshot"),folder)
    shot=_asset(f.get("screenshot"),folder)
    check='<span class="tag">Needs a look</span>' if f.get("confidence")=="suspected" else ""
    measured=_observed(f)
    image=('<figure class="capture"><img src="'+esc(before)+'" alt="The element as Chromium drew it">'
           '<figcaption>As Chromium drew it at '+esc(f.get("viewport",""))+' px</figcaption></figure>') if before and not compared else ""
    evidence=esc(json.dumps(f.get("evidence") or {},ensure_ascii=False,indent=2))
    details=('<details class="more"><summary>Measurements and element</summary><dl>'
             '<div><dt>Page</dt><dd>'+_safe_link(f.get("url",""))+'</dd></div>'
             '<div><dt>Element</dt><dd><code>'+esc(f.get("selector",""))+'</code></dd></div>'
             '<div><dt>Checked at</dt><dd>'+esc(_widths(f))+'</dd></div>'
             +('<div><dt>Screenshot</dt><dd><a href="'+esc(shot)+'" target="_blank" rel="noopener noreferrer">Whole page at '+esc(f.get("viewport",""))+' px</a></dd></div>' if shot else "")
             +'</dl><pre>'+evidence+'</pre></details>')
    return ('<article class="card '+esc(severity)+('' if image else ' no-image')+'" id="finding-'+esc(f.get("id",""))+'">'
            '<div class="card-body"><p class="card-top"><span class="sev">'+esc(word)+'</span>'
            '<span class="where">'+esc(_where(f))+'</span>'+check+'</p>'
            +('<p class="sample" lang="'+_lang_of(sample)+'">'+esc(sample)+'</p>' if sample else "")
            +(('<p class="measured">'+esc(measured)+'</p>') if measured else "")
            +_sequences(f)+_explanation(f)+_repair(f,folder,before)+details+'</div>'+image+'</article>')


def _group(detector, findings, folder):
    title,why,_=FINDING_COPY.get(detector,("Rendering observation","Measurements are available for review.",""))
    count=(' <span class="count">'+_label(len(findings),"place")+'</span>') if len(findings)>1 else ""
    return ('<section class="group"><h3>'+esc(title)+count+'</h3><p class="why">'+esc(why)+'</p>'
            +"".join(_card(f,folder) for f in findings)+'</section>')


def _summary_sentence(counts):
    parts=[]
    if counts["error"]:
        parts.append(_label(counts["error"],"problem")+" to fix")
    if counts["warning"]:
        parts.append(_label(counts["warning"],"thing")+" to check")
    if counts["info"]:
        parts.append(_label(counts["info"],"note"))
    if not parts:
        return "Nothing broke in these checks."
    text=parts[0] if len(parts)==1 else ", ".join(parts[:-1])+" and "+parts[-1]
    return text[0].upper()+text[1:]+"."


def _ai_line(data):
    ai=data.get("ai") or {}
    if not ai.get("calls"):
        return ""
    tokens=int(ai.get("input_tokens") or 0)+int(ai.get("output_tokens") or 0)
    return ('<p class="meta">Explanations and repairs by BharatCode <code>'+esc(ai.get("model",""))+'</code>: '
            +_label(int(ai["calls"]),"call")+(", "+_label(tokens,"token") if tokens else "")
            +(", "+esc(f'{float(ai.get("seconds") or 0):g}')+" s" if ai.get("seconds") else "")+'.</p>')


LOGO=('<svg class="logo" viewBox="0 0 120 120" aria-hidden="true">'
      '<path d="M49.65 21.36 A40 40 0 1 1 49.65 98.64" fill="none" stroke="#0E6B4E" stroke-width="13" stroke-linecap="round"/>'
      '<g fill="#D9475A"><circle cx="34.83" cy="91.08" r="6.5"/><circle cx="24.05" cy="77.54" r="6.5"/>'
      '<circle cx="20" cy="60" r="6.5"/><circle cx="24.05" cy="42.46" r="6.5"/><circle cx="34.83" cy="28.92" r="6.5"/></g></svg>')

CSS=r"""
@font-face{font-family:'Anek Latin';src:url('font-anek-latin-400.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:'Anek Latin';src:url('font-anek-latin-600.woff2') format('woff2');font-weight:600;font-display:swap}
@font-face{font-family:'Anek Devanagari';src:url('font-anek-devanagari-400.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:'Anek Devanagari';src:url('font-anek-devanagari-600.woff2') format('woff2');font-weight:600;font-display:swap}
@font-face{font-family:'Anek Kannada';src:url('font-anek-kannada-400.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:'Anek Kannada';src:url('font-anek-kannada-600.woff2') format('woff2');font-weight:600;font-display:swap}
:root{color-scheme:only light;--paper:#F6F7F2;--sheet:#FFFEFB;--ink:#1B2440;--soft:#4A5064;--line:#D9DED3;--rule:#DCE6F2;
--green:#0E6B4E;--green-tint:#E3F1EA;--red:#D9475A;--red-text:#B8323F;--red-tint:#FBE7E9;--amber:#8A5208;--amber-tint:#FBF0DC;
--font:'Anek Latin','Anek Devanagari','Anek Kannada','Nirmala UI',system-ui,sans-serif;--mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace}
*{box-sizing:border-box}html{background:var(--paper)}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 var(--font);-webkit-font-smoothing:antialiased}
:lang(hi){font-family:'Anek Devanagari','Anek Latin',sans-serif}:lang(kn){font-family:'Anek Kannada','Anek Latin',sans-serif}
a{color:var(--green)}a:focus-visible,summary:focus-visible{outline:3px solid var(--green);outline-offset:3px;border-radius:3px}
code,pre{font-family:var(--mono);font-size:13px}
h1,h2,h3,p,dl,dd,ul,ol,figure{margin:0}
.shell{max-width:980px;margin:0 auto;padding:0 clamp(16px,4vw,32px)}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:68px;border-bottom:1px solid var(--line)}
.brand{display:flex;align-items:center;gap:10px;font-size:19px;font-weight:600;text-decoration:none;color:var(--ink)}
.logo{width:28px;height:28px}
.downloads{font-size:14px;color:var(--soft)}.downloads a{margin-left:14px}
.head{padding:40px 0 32px;border-bottom:1px solid var(--line)}
.head h1{font-size:clamp(24px,3.4vw,32px);line-height:1.2;font-weight:600;letter-spacing:-.01em;overflow-wrap:anywhere}
.head h1 a{color:inherit;text-decoration:none}.head h1 a:hover{text-decoration:underline;text-underline-offset:5px}
.verdict{margin-top:14px;font-size:clamp(19px,2.4vw,22px);line-height:1.4}
.meta{margin-top:8px;color:var(--soft);font-size:15px}.meta code{font-size:13px;color:var(--ink)}
.notice{margin-top:18px;padding:12px 14px;border-radius:6px;background:var(--amber-tint);color:var(--amber);font-size:15px}
.notice strong{font-weight:600}
.band{padding-top:36px}
.band>h2{display:flex;align-items:baseline;gap:10px;font-size:22px;font-weight:600;padding-bottom:10px;border-bottom:2px solid var(--ink)}
.band>h2 .n{font-size:16px;color:var(--soft);font-weight:400}
.group{padding-top:26px}
.group h3{font-size:19px;font-weight:600}.group h3 .count{font-size:15px;font-weight:400;color:var(--soft);margin-left:6px}
.why{margin-top:4px;color:var(--soft);max-width:68ch}
.card{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,300px);gap:24px;margin-top:14px;padding:20px 22px;background:var(--sheet);border:1px solid var(--line);border-radius:10px}
.card.no-image{grid-template-columns:minmax(0,1fr)}
.card-top{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;font-size:14px;color:var(--soft)}
.sev{font-weight:600;padding:2px 9px;border-radius:4px;font-size:14px}
.error .sev{background:var(--red-tint);color:var(--red-text)}.error .sev:before{content:'✗ '}
.warning .sev{background:var(--amber-tint);color:var(--amber)}
.info .sev{background:#E8EEF7;color:#3B4F73}
.tag{font-size:13px;border:1px solid var(--line);border-radius:4px;padding:1px 7px}
.sample{margin-top:12px;font-size:22px;line-height:1.6;overflow-wrap:anywhere}
.measured{margin-top:4px;color:var(--soft)}
.sequences{list-style:none;padding:0;margin-top:10px;display:grid;gap:6px}
.sequences li{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 12px}
.glyph{font-size:24px;line-height:1.3;min-width:2ch;color:var(--red-text)}
.sequences code{background:var(--paper);padding:1px 6px;border-radius:3px}
.seq-why{color:var(--soft);font-size:14px}
.ai{margin-top:16px;padding:14px 16px;border-radius:8px;background:#F1F4FA}
.ai-label{font-size:14px;font-weight:600;color:#3B4F73;margin-bottom:4px}
.ai p+p{margin-top:8px}
.translation{display:grid;grid-template-columns:4.5em minmax(0,1fr);gap:8px;font-size:16px;line-height:1.65}
.lang-name{color:var(--soft);font-size:14px;padding-top:2px}
.repair{margin-top:14px;padding:14px 16px;border-radius:8px;border:1px solid var(--line)}
.repair-title{font-weight:600}
.repair.ok{background:var(--green-tint);border-color:transparent}.repair.ok .repair-title{color:var(--green)}
.repair.bad .repair-title{color:var(--red-text)}
.repair pre{margin-top:8px;padding:10px 12px;background:#fff;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere}
.repair .next{margin-top:8px}.muted{color:var(--soft);margin-top:6px;font-size:14px}
.compare{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}.compare.single{grid-template-columns:minmax(0,420px)}
.compare figure,.capture{background:#fff;border:1px solid var(--line);border-radius:6px;padding:8px}
.compare img,.capture img{display:block;max-width:100%;height:auto;margin:0 auto}
figcaption{margin-top:6px;font-size:13px;color:var(--soft);text-align:center}
.capture{align-self:start}
.attempts{margin-top:12px}.attempts-title{font-size:14px;color:var(--soft)}
.attempts ol{list-style:none;padding:0;margin-top:6px;display:grid;gap:4px}
.attempts li{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;font-size:14px}
.attempts .mark{font-weight:600}.attempts .ok .mark{color:var(--green)}.attempts .bad .mark{color:var(--red-text)}
.attempts code{background:#fff;padding:1px 6px;border-radius:3px;overflow-wrap:anywhere}
.more{margin-top:14px;font-size:14px}.more summary{cursor:pointer;color:var(--green);font-weight:600;width:fit-content}
.more dl{margin-top:10px;display:grid;gap:6px}.more dl div{display:grid;grid-template-columns:7em minmax(0,1fr);gap:10px}
.more dt{color:var(--soft)}.more dd{overflow-wrap:anywhere}
.more pre{margin-top:10px;padding:12px;background:var(--paper);border:1px solid var(--line);border-radius:6px;max-height:240px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere}
details.notes>summary{cursor:pointer;list-style:none;display:flex;align-items:baseline;gap:10px;font-size:22px;font-weight:600;padding-bottom:10px;border-bottom:2px solid var(--ink)}
details.notes>summary::-webkit-details-marker{display:none}
details.notes>summary:after{content:'Show';margin-left:auto;font-size:15px;font-weight:600;color:var(--green)}
details.notes[open]>summary:after{content:'Hide'}
details.notes>summary .n{font-size:16px;color:var(--soft);font-weight:400}
.clean{margin-top:30px;padding:20px;border-radius:10px;background:var(--green-tint);color:var(--green);font-size:18px}
.foot{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 20px;margin-top:56px;padding:22px 0 40px;border-top:1px solid var(--line);font-size:14px;color:var(--soft)}
@media(max-width:720px){.card{grid-template-columns:minmax(0,1fr);gap:14px;padding:16px}.capture{order:-1;max-width:420px}
.compare{grid-template-columns:1fr}.downloads a{margin-left:10px}.translation{grid-template-columns:1fr;gap:0}.more dl div{grid-template-columns:1fr;gap:0}}
@media print{.downloads,.more summary{display:none}.card{break-inside:avoid}details.notes>.group{display:block}}
"""


def _html_report(data,folder):
    findings=data.get("findings",[])
    counts=Counter(f.get("severity","info") for f in findings)
    target=data.get("target","")
    groups=defaultdict(lambda:defaultdict(list))
    for f in findings:
        groups[f.get("severity","info")][f.get("detector","unknown")].append(f)
    bands=[]
    for severity in ORDER:
        if severity not in groups:
            continue
        detectors=sorted(groups[severity].items(),key=lambda pair:(-len(pair[1]),pair[0]))
        body="".join(_group(d,items,folder) for d,items in detectors)
        title=SEVERITY[severity][1]
        number='<span class="n">'+str(counts[severity])+'</span>'
        if severity=="info":
            bands.append('<section class="band"><details class="notes"><summary>'+title+' '+number+'</summary>'+body+'</details></section>')
        else:
            bands.append('<section class="band"><h2>'+title+' '+number+'</h2>'+body+'</section>')
    if not bands:
        bands.append('<p class="clean">✓ Nothing broke in these checks. That covers this page at these widths, not every page on the site.</p>')

    notices=[]
    if data.get("demo_mode"):
        notices.append('<p class="notice"><strong>Offline development demo.</strong> No BharatCode model call was made. Sample repairs are predefined rules.</p>')
    if any("error" in page for page in data.get("pages",[])):
        notices.append('<p class="notice"><strong>Incomplete scan.</strong> Some pages or screen widths could not be checked. Missing data is not clean data.</p>')
    if not data.get("engine_version"):
        notices.append('<p class="notice"><strong>Earlier scan data.</strong> These findings come from an older scanner. Run a fresh scan to apply the latest detection rules.</p>')

    widths=sorted({w for f in findings for w in (f.get("viewports") or [f.get("viewport")]) if w}
                  or {p.get("viewport") for p in data.get("pages",[]) if p.get("viewport")})
    width_text=" and ".join(("phone" if w<=430 else "tablet" if w<=1024 else "desktop")+f" ({w} px)" for w in widths)
    when=_when(data.get("generated_at"))
    checked=("Checked in Chromium"+(" at "+width_text if width_text else "")+(" on "+when if when else "")+".")
    name=_page_name(target)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="only light">'
        '<title>'+esc(name)+' | AksharaCheck report</title><style>'+CSS+'</style></head><body>'
        '<header class="shell"><div class="top"><span class="brand">'+LOGO+'AksharaCheck</span>'
        '<nav class="downloads" aria-label="Downloads">Download <a href="report.json">JSON</a><a href="report.md">Markdown</a></nav></div></header>'
        '<main class="shell"><section class="head" aria-labelledby="report-title">'
        '<h1 id="report-title">'+_safe_link(target,name)+'</h1>'
        '<p class="verdict">'+esc(_summary_sentence(counts))+'</p>'
        '<p class="meta">'+esc(checked)+'</p>'+_ai_line(data)+''.join(notices)+'</section>'
        +"".join(bands)+'</main>'
        '<footer class="shell"><div class="foot"><span>AksharaCheck measures how Chromium draws the page. It is not a full accessibility audit.</span>'
        '<span><span lang="hi">अक्षर जाँच</span> · <span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span></span></div></footer></body></html>'
    )


def _copy_fonts(folder):
    for name in FONT_FILES:
        source=ASSETS/name
        if source.is_file() and not (folder/name).is_file():
            shutil.copyfile(source,folder/name)


def _markdown(data):
    findings=data.get("findings",[])
    counts=Counter(f.get("severity","info") for f in findings)
    lines=["# AksharaCheck report: "+_page_name(data.get("target","")),"",
           _summary_sentence(counts),"","Page: "+str(data.get("target","")),""]
    if data.get("demo_mode"):
        lines+=["Offline development demo. No BharatCode model was called.",""]
    ai=data.get("ai") or {}
    if ai.get("calls"):
        lines+=[f"Explanations and repairs by BharatCode {ai.get('model','')} ({ai['calls']} calls).",""]
    for severity in ORDER:
        items=[f for f in findings if f.get("severity","info")==severity]
        if not items:
            continue
        lines+=["## "+SEVERITY[severity][1],""]
        for f in items:
            title,_,action=FINDING_COPY.get(f.get("detector"),("Observation","","Review the element."))
            fix=f.get("fix") or {}
            lines+=["### "+SEVERITY[severity][0]+": "+title,""]
            if f.get("sample"):
                lines+=["> "+str(f["sample"]),""]
            measured=_observed(f)
            if measured:
                lines+=[measured,""]
            for item in (f.get("evidence") or {}).get("invalid_sequences") or []:
                lines.append("- `"+" ".join(item.get("codepoints") or [])+"`: "+str(item.get("reason","")))
            if f.get("ai_explanation"):
                lines+=["","BharatCode: "+str(f["ai_explanation"])]
                for code,label in (("hi","हिंदी"),("kn","ಕನ್ನಡ")):
                    if f.get("summary_"+code):
                        lines.append(label+": "+str(f["summary_"+code]))
            if fix.get("status")=="verified":
                lines+=["","Fix verified in Chromium at "+str(fix.get("viewport") or f.get("viewport"))+" px:","","```css",_css_text(fix),"```"]
            elif fix.get("status")=="unverified":
                lines+=["","No suggested fix passed: "+str(fix.get("reason","")),"","What to change: "+action]
            else:
                lines+=["","What to change: "+action]
            for t in fix.get("attempts") or []:
                lines.append("- Tried `"+_css_text(t).replace("\n"," ")+"`: "+("passed" if t.get("status")=="verified" else "rejected, "+str(t.get("reason",""))))
            lines+=["","Element: `"+str(f.get("selector",""))+"` on "+str(f.get("url","")),""]
    return "\n".join(lines)


def write_reports(data,dest):
    folder=Path(dest)
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"report.json").write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
    (folder/"report.md").write_text(_markdown(data),encoding="utf-8")
    _copy_fonts(folder)
    (folder/"report.html").write_text(_html_report(data,folder),encoding="utf-8")
