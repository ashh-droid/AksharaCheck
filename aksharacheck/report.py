"""Generate JSON, Markdown and a standalone HTML report.

The HTML report needs no network: styles and the favicon are embedded, while
Anek fonts are copied next to the report. Optional JavaScript improves offline
downloads and language selection; findings remain readable without JavaScript.
Everything that comes from a scanned site is HTML-escaped.
"""
from __future__ import annotations

import html
import re
import json
import base64
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

# Embedded favicon: no relative paths to break when the HTML report is opened
# from file:// or from a copied report directory on GitHub Pages.
REPORT_FAVICON_SVG='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="7" fill="#141B30"/>
<path d="M13.26 8.48 A8 8 0 1 1 13.26 23.52" fill="none" stroke="#3FB58A" stroke-width="3" stroke-linecap="round"/>
<circle cx="9.87" cy="21.14" r="1.5" fill="#F07A88"/>
<circle cx="8" cy="16" r="1.5" fill="#F07A88"/>
<circle cx="9.87" cy="10.86" r="1.5" fill="#F07A88"/>
</svg>'''
REPORT_FAVICON="data:image/svg+xml;base64,"+base64.b64encode(REPORT_FAVICON_SVG.encode("utf-8")).decode("ascii")



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
    return "Seen on "+" and ".join(k.lower() for k in kinds)


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


LANG_NAMES={"en":"English","hi":"Hindi","kn":"Kannada","mr":"Marathi","ne":"Nepali","sa":"Sanskrit","tcy":"Tulu",
            "kok":"Konkani","mai":"Maithili","bho":"Bhojpuri"}


def _lang_name(code):
    code=str(code or "").strip()
    if not code:
        return "no language"
    name=LANG_NAMES.get(code.lower().split("-")[0])
    return f"{name} ({code})" if name else code


def _font_names(value):
    names=[part.strip().strip("'\"") for part in str(value or "").split(",")]
    names=[n for n in names if n and n.lower() not in {"serif","sans-serif","monospace","system-ui","cursive","fantasy"}]
    return ", ".join(names) or str(value or "")


def _duration(seconds):
    seconds=float(seconds or 0)
    if seconds<60:
        return f"{seconds:.0f} s" if seconds>=10 else f"{seconds:.1f} s"
    minutes,rest=divmod(round(seconds),60)
    return f"{minutes} min {rest} s" if rest else f"{minutes} min"


def _mostly(text,low,high):
    letters=[c for c in str(text or "") if c.isalpha()]
    return bool(letters) and sum(low<=ord(c)<=high for c in letters)/len(letters)>=.6


def _observed(f):
    """Short, detector-specific measurement in plain words. Do not repeat the category's prose."""
    details=f.get("evidence") or {}
    kind=f.get("detector")
    if kind=="possible-clipping":
        amount=details.get("overflow_pixels")
        if amount is None:
            amount=max(0,float(details.get("scroll_height") or 0)-float(details.get("client_height") or 0))
        return f"The text needs {round(float(amount),1):g} px more height than its box gives it."
    if kind=="mobile-overflow":
        amount=max(0,float(details.get("scroll_width") or 0)-float(details.get("client_width") or 0))
        return f"At phone width the line runs {round(amount,1):g} px past its box."
    if kind=="tight-line-height":
        return f"Line height is {details.get('ratio','not measured')} times the font size."
    if kind=="font-fallback":
        actual=[a.get("familyName") for a in details.get("actual") or [] if isinstance(a,dict) and a.get("familyName")]
        asked=_font_names(details.get("requested")) or "another font"
        return ("The page asked for "+asked+", but Chromium drew this text with "+" and ".join(dict.fromkeys(actual))+"."
                if actual else "The page asked for "+asked+".")
    if kind=="font-load-failed":
        status=details.get("status")
        return f"The font file returned HTTP {status}." if status else "The font file could not be downloaded."
    if kind=="wrong-lang":
        return ("Tagged as "+_lang_name(details.get("effective"))+", but written in "
                +str(details.get("script","an Indic script")).capitalize()+".")
    if kind=="mixed-language":
        scripts=details.get("scripts") or {}
        parts=[f"{name.capitalize()} ({count} letters)" for name,count in scripts.items()]
        return ("One element mixes "+" and ".join(parts)+" under the tag "+_lang_name(details.get("effective"))+"."
                if parts else "More than one script appears in one element.")
    if kind=="legacy-font":
        return "Font used: "+_font_names(details.get("computed_font")) +"."
    return ""


def _merged_sequences(items):
    """Overlapping windows around one mistake (such as माा and ााि) become one sequence."""
    merged=[]
    for item in sorted(items,key=lambda x:int(x.get("position",0))):
        seq=str(item.get("sequence","")); codes=list(item.get("codepoints") or []); pos=int(item.get("position",0))
        if merged and 0<pos-merged[-1]["position"]<len(seq):
            step=pos-merged[-1]["position"]
            merged[-1]["sequence"]+=seq[-step:]
            merged[-1]["codepoints"]+=codes[-step:]
            merged[-1]["position"]=pos
        else:
            merged.append({"position":pos,"sequence":seq,"codepoints":codes,"reason":str(item.get("reason",""))})
    return merged


PLAIN_REASONS={
    "dependent vowel sign without a preceding consonant":"A vowel sign with no letter before it",
    "nukta without a preceding consonant":"A nukta dot with no letter before it",
    "virama without a preceding consonant":"A virama (halant) with no letter before it",
    "final mark without a preceding syllable":"A mark with no syllable before it",
}


def _sequences(f):
    """The exact characters of each broken letter, the evidence a developer can search for."""
    items=_merged_sequences((f.get("evidence") or {}).get("invalid_sequences") or [])
    if not items:
        return ""
    rows=[]
    for item in items[:6]:
        seq=item["sequence"].strip()
        reason=PLAIN_REASONS.get(item["reason"].lower(),item["reason"].capitalize())
        rows.append('<li><span class="glyph" lang="'+_lang_of(seq)+'">'+esc(seq)+'</span>'
                    '<span class="seq-text"><span class="seq-why">'+esc(reason)+'</span>'
                    '<code>'+" ".join(esc(c) for c in item["codepoints"])+'</code></span></li>')
    return '<ul class="sequences" aria-label="The broken letters">'+"".join(rows)+'</ul>'


def _css_text(change):
    lines=[f"{k}: {v};" for k,v in (change.get("css") or {}).items()]
    lines+=[f'{k}="{v}"' for k,v in (change.get("attributes") or {}).items()]
    return "\n".join(lines)


SELECTOR_NOISE=re.compile(r"(?:\s+(?:selected|identified|matched|targeted)\s+by)?\s*\(?\[?data-akshara-id=[\"']?ak-[a-z0-9-]+[\"']?\]?\)?|\bak-[a-f0-9]{6,}\b",re.I)


def _clean(text):
    """Remove internal element handles a model may have echoed into prose."""
    return re.sub(r"\s+"," ",SELECTOR_NOISE.sub("",str(text or ""))).replace(" ,",",").replace(" .",".").strip()


def _explanation(f):
    english=_clean(f.get("ai_explanation"))
    # Placeholder text from an unavailable model is not an explanation.
    if not english or english.startswith(("BharatCode unavailable","AI unavailable","BharatCode API")):
        return ""
    panes=[("en","English",english)]
    for code,name,low,high in (("hi","हिंदी",0x0900,0x097F),("kn","ಕನ್ನಡ",0x0C80,0x0CFF)):
        text=_clean(f.get("summary_"+code))
        if text and _mostly(text,low,high):
            panes.append((code,name,text))
    if len(panes)==1:
        return '<div class="ai"><div class="ai-head"><p class="ai-label">What BharatCode says</p></div><p class="pane p-en">'+esc(english)+'</p></div>'
    # One language at a time. Radio buttons keep the switch working without JavaScript.
    key="l-"+re.sub(r"[^a-zA-Z0-9-]","",str(f.get("id","x")))
    radios="".join('<input class="sr-only t-'+code+'" type="radio" name="'+key+'" id="'+key+'-'+code+'"'+(' checked' if n==0 else '')+'>'
                   for n,(code,_,_) in enumerate(panes))
    labels="".join('<label for="'+key+'-'+code+'" class="tab-'+code+'"'+('' if code=="en" else ' lang="'+code+'"')+'>'+esc(name)+'</label>'
                   for code,name,_ in panes)
    texts="".join('<p class="pane p-'+code+'"'+('' if code=="en" else ' lang="'+code+'"')+'>'+esc(text)+'</p>' for code,_,text in panes)
    return ('<div class="ai">'+radios+'<div class="ai-head"><p class="ai-label">What BharatCode says</p>'
            '<span class="tabs" role="group" aria-label="Language">'+labels+'</span></div><div class="panes">'+texts+'</div></div>')


def _attempts(fix):
    tries=fix.get("attempts") or []
    if not tries or (len(tries)==1 and tries[0].get("status")=="verified"):
        return ""
    rejected=sum(1 for t in tries if t.get("status")!="verified")
    rows=[]
    for t in tries:
        ok=t.get("status")=="verified"
        rows.append('<li class="'+("ok" if ok else "bad")+'"><span class="mark">'+(CHECK if ok else CROSS)+'</span>'
                    '<code>'+esc(_css_text(t).replace("\n"," "))+'</code>'
                    '<span>'+("Passed" if ok else "Rejected: "+esc(t.get("reason") or "did not pass"))+'</span></li>')
    if rejected<len(tries):
        summary="BharatCode tried "+_label(len(tries),"repair")+". Chromium rejected "+str(rejected)+" before one passed."
    else:
        summary="BharatCode tried "+_label(len(tries),"repair")+". Chromium rejected each one."
    return '<details class="attempts"><summary>'+esc(summary)+'</summary><ol>'+"".join(rows)+'</ol></details>'


def _repair(f, ai_ran=False):
    """What to do next: a verified fix, a failed attempt with its reasons, or a change to make by hand."""
    _,_,action=FINDING_COPY.get(f.get("detector"),("","","Review the element on the page."))
    fix=f.get("fix") or {}
    state=fix.get("status")
    width=fix.get("viewport") or f.get("viewport")
    if state=="verified":
        lang=(fix.get("attributes") or {}).get("lang")
        if lang and not fix.get("css"):
            how=f"Add this attribute to the element, so browsers and screen readers treat the text as {LANG_NAMES.get(lang,lang)}."
        else:
            how="Ask your developer to add this CSS to the element. With it the whole text shows, at full size."
        return ('<div class="repair ok"><p class="repair-title">'+CHECK+'Fix ready, tested in Chromium at '
                +esc(width)+' px</p><p class="repair-note">'+esc(how)+'</p><pre>'+esc(_css_text(fix))+'</pre>'+_attempts(fix)+'</div>')
    if state=="unverified":
        reason=str(fix.get("reason") or "it did not pass the browser check").rstrip(".")
        return ('<div class="todo"><p class="todo-title">What to change</p><p>'+esc(action)+'</p>'
                '<p class="todo-note">No suggested fix passed in Chromium: '+esc(reason[0].lower()+reason[1:])+'.</p>'+_attempts(fix)+'</div>')
    if state=="unavailable":
        note='<p class="todo-note">BharatCode could not answer for this one, so there is no explanation or suggested fix.</p>'
    elif ai_ran and f.get("severity")!="info" and not _explanation(f):
        note='<p class="todo-note">BharatCode was not asked about this one in this run.</p>'
    else:
        note=""
    return '<div class="todo"><p class="todo-title">What to change</p><p>'+esc(action)+'</p>'+note+'</div>'


def _figures(f, folder):
    """How Chromium drew the element, and after a verified CSS fix, how it looks now. Shown large, under the text."""
    before=_usable_crop(f.get("element_screenshot"),folder)
    fix=f.get("fix") or {}
    after=_usable_crop(fix.get("after_screenshot"),folder) if fix.get("status")=="verified" and fix.get("css") else ""
    width=f.get("viewport","")
    parts=[]
    if before:
        parts.append('<figure><img src="'+esc(before)+'" alt="The element as Chromium drew it">'
                     '<figcaption>'+("Before the fix" if after else "How Chromium drew it"+(f" at {esc(width)} px" if width else ""))+'</figcaption></figure>')
    if after:
        parts.append('<figure class="after"><img src="'+esc(after)+'" alt="The element after the fix">'
                     '<figcaption>After the fix</figcaption></figure>')
    return '<div class="figures'+(' pair' if after else '')+'">'+"".join(parts)+'</div>' if parts else ""


def _card(f, folder, ai_ran=False):
    severity=f.get("severity","info")
    word=SEVERITY.get(severity,SEVERITY["info"])[0]
    sample=str(f.get("sample") or "").strip()
    if len(sample)>220:
        sample=sample[:217]+"…"
    details=f.get("evidence") or {}
    if not sample and f.get("detector")=="font-load-failed" and details.get("font_url"):
        sample_html='<p class="sample code"><code>'+esc(details["font_url"])+'</code></p>'
    else:
        sample_html='<p class="sample" lang="'+_lang_of(sample)+'">'+esc(sample)+'</p>' if sample else ""
    check='<span class="tag">Confirm with the screenshot</span>' if f.get("confidence")=="suspected" else ""
    measured=_observed(f)
    shot=_asset(f.get("screenshot"),folder)
    figures=_figures(f,folder)
    raw=esc(json.dumps(details,ensure_ascii=False,indent=2))
    more=('<details class="more"><summary>Technical details</summary><dl>'
          '<div><dt>Page</dt><dd>'+_safe_link(f.get("url",""))+'</dd></div>'
          +'<div><dt>Checked at</dt><dd>'+esc(_widths(f))+'</dd></div>'
          +('<div><dt>Screenshot</dt><dd><a href="'+esc(shot)+'" target="_blank" rel="noopener noreferrer">Whole page at '+esc(f.get("viewport",""))+' px</a></dd></div>' if shot else "")
          +'</dl><pre>'+raw+'</pre></details>')
    evidence=sample_html+(('<p class="measured">'+esc(measured)+'</p>') if measured else "")+_sequences(f)
    return ('<article class="card '+esc(severity)+'" id="finding-'+esc(f.get("id",""))+'">'
            '<p class="card-top"><span class="sev">'+esc(word)+'</span>'
            '<span class="where">'+esc(_where(f))+'</span>'+check+'</p>'
            '<div class="evidence'+('' if figures else ' no-figures')+'"><div class="ev-text"><p class="label">On the page</p>'+evidence+'</div>'+figures+'</div>'
            '<div class="steps">'+_explanation(f)+_repair(f,ai_ran)+'</div>'+more+'</article>')


def _group(detector, findings, folder, ai_ran=False):
    title,why,_=FINDING_COPY.get(detector,("Rendering observation","Measurements are available for review.",""))
    count=(' <span class="count">'+_label(len(findings),"place")+'</span>') if len(findings)>1 else ""
    return ('<section class="group" id="'+esc(detector)+'"><h3>'+esc(title)+count+'</h3><p class="why">'+esc(why)+'</p>'
            +"".join(_card(f,folder,ai_ran) for f in findings)+'</section>')


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


def _ai_counts(data):
    """Findings BharatCode explained, findings it could have been asked about, and whether it ran at all."""
    findings=data.get("findings",[])
    eligible=[f for f in findings if f.get("severity")!="info"]
    explained=sum(1 for f in findings if _explanation(f))
    ai=data.get("ai") or {}
    ran=bool(int(ai.get("calls") or 0) or int(ai.get("resumed_findings") or 0) or explained)
    return explained,len(eligible),ran


def _ai_line(data):
    ai=data.get("ai") or {}
    explained,eligible,ran=_ai_counts(data)
    if not ran:
        return ""
    live=int(ai.get("calls") or 0)
    resumed=int(ai.get("resumed_findings") or 0)
    tokens=int(ai.get("input_tokens") or 0)+int(ai.get("output_tokens") or 0)
    model=esc(ai.get("model") or "")
    first=(f"BharatCode <code>{model}</code> explained {explained} of the {eligible} findings to fix or check"
           if eligible else f"BharatCode <code>{model}</code> explained {explained} findings")
    usage=[]
    if live:
        usage.append(_label(live,"model call"))
    if tokens:
        usage.append(_label(tokens,"token"))
    if live and ai.get("seconds"):
        usage.append(_duration(ai["seconds"]))
    text=first+(" ("+esc(", ".join(usage))+")" if usage else "")+"."
    if resumed:
        text+=(" "+esc(_label(resumed,"explanation"))+" "+("comes" if resumed==1 else "come")
               +" from an earlier run; "+("its" if resumed==1 else "their")+" fixes were tested again in Chromium.")
    return '<p class="meta">'+text+'</p>'


def _overview(groups, counts):
    """A contents list: every kind of problem, how often, and where it stands."""
    rows=[]
    for severity in ORDER:
        for detector,items in sorted(groups.get(severity,{}).items(),key=lambda pair:(-len(pair[1]),pair[0])):
            title=FINDING_COPY.get(detector,("Rendering observation",))[0]
            verified=sum(1 for f in items if (f.get("fix") or {}).get("status")=="verified")
            failed=sum(1 for f in items if (f.get("fix") or {}).get("status")=="unverified")
            if verified and verified==len(items):
                state='<span class="state ok">'+CHECK+'Fix ready</span>'
            elif verified:
                state='<span class="state ok">'+CHECK+str(verified)+' of '+str(len(items))+' fixes ready</span>'
            elif detector in {"broken-cluster","legacy-font","mixed-language"}:
                state='<span class="state">Edit the text</span>'
            elif failed or detector=="font-load-failed":
                state='<span class="state">Needs a developer</span>'
            else:
                state='<span class="state">Take a look</span>'
            rows.append('<li class="'+severity+'"><span class="sev">'+SEVERITY[severity][0]+'</span>'
                        '<a href="#'+esc(detector)+'">'+esc(title)+'</a><span class="places">'+_label(len(items),"place")+'</span>'+state+'</li>')
    total=sum(counts.values()) or 1
    bar="".join(f'<span class="seg {k}" style="flex:{counts[k]}"></span>' for k in ORDER if counts[k])
    legend="".join(f'<li class="{k}"><span class="dot"></span>{counts[k]} {SEVERITY[k][1].lower()}</li>' for k in ORDER if counts[k])
    return ('<section class="overview" aria-labelledby="overview-title"><div class="overview-head"><h2 id="overview-title">What was found</h2>'
            '<div class="meter" role="img" aria-label="'+esc(_summary_sentence(counts))+'"><span class="bar">'+bar+'</span><ul>'+legend+'</ul></div></div>'
            '<ol class="contents">'+"".join(rows)+'</ol>'
            '<dl class="key" aria-label="What the labels mean">'
            '<div class="error"><dt><span class="sev">Fix</span></dt><dd>Readers see broken text. Start here.</dd></div>'
            '<div class="warning"><dt><span class="sev">Check</span></dt><dd>Likely wrong. Check the screenshot.</dd></div>'
            '<div class="info"><dt><span class="sev">Note</span></dt><dd>Worth knowing. Often fine as it is.</dd></div></dl></section>') if total and rows else ""


CHECK='<svg class="ico" viewBox="0 0 16 16" aria-hidden="true"><path d="M3 8.5l3.2 3.2L13 4.8"/></svg>'
CROSS='<svg class="ico" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8"/></svg>'
DOWNLOAD='<svg class="ico" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 2.5v8M4.5 7.5L8 11l3.5-3.5M3 13.5h10"/></svg>'

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
:root{color-scheme:only light;--paper:#F6F7F2;--sheet:#FFFEFB;--ink:#1B2440;--soft:#4A5064;--faint:#6B7185;--line:#D9DED3;--rule:#DCE6F2;--page:#ECEEE7;--panel:#F4F5F0;--edge:#C8CFC1;
--green:#0E6B4E;--green-tint:#E3F1EA;--red:#D9475A;--red-text:#B8323F;--red-tint:#FBE7E9;--amber:#8A5208;--amber-tint:#FBF0DC;--amber-bar:#E2A33B;
--blue:#3B4F73;--blue-tint:#E8EEF7;--blue-bar:#8FA3C4;--ai:#F1F4FA;--night:#141B30;--night-2:#1C2541;--night-soft:#AAB3CC;--night-green:#3FB58A;
--font:'Anek Latin','Anek Devanagari','Anek Kannada','Nirmala UI',system-ui,sans-serif;--mono:ui-monospace,'SF Mono',Menlo,Consolas,monospace}
*{box-sizing:border-box}html{background:var(--page);scroll-behavior:smooth;scroll-padding-top:20px}
body{margin:0;background:var(--page);color:var(--ink);font:17px/1.6 var(--font);-webkit-font-smoothing:antialiased}
:lang(hi){font-family:'Anek Devanagari','Anek Latin',sans-serif}:lang(kn){font-family:'Anek Kannada','Anek Latin',sans-serif}
a{color:var(--green)}a:focus-visible,summary:focus-visible{outline:3px solid var(--green);outline-offset:3px;border-radius:3px}
code,pre{font-family:var(--mono);font-size:13px}
h1,h2,h3,p,dl,dd,ul,ol,figure{margin:0}h1,h2,h3{font-weight:600;letter-spacing:-.01em}
.shell{max-width:1040px;margin:0 auto;padding:0 clamp(16px,4vw,32px)}
/* Header: the same lockup as the website */
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:96px}
.brand{display:flex;align-items:center;gap:14px;color:var(--ink);text-decoration:none}
.logo{width:48px;height:48px;flex:none}
.brand-text{display:flex;flex-direction:column;gap:5px}
.brand-name{font-size:30px;font-weight:600;line-height:1;letter-spacing:-.02em}
.brand-sub{display:flex;gap:12px;font-size:15px;line-height:1.2;color:var(--soft)}
.downloads{display:flex;gap:10px}
.downloads a{display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border:1px solid var(--edge);border-radius:8px;background:#fff;color:var(--ink);font-size:15px;font-weight:600;line-height:1;text-decoration:none;box-shadow:0 1px 2px rgba(27,36,64,.06)}
.downloads a:hover{border-color:var(--green);color:var(--green)}
.downloads .ico{width:16px;height:16px}
.ico{display:inline-block;flex:none;width:1em;height:1em;vertical-align:-.12em;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
/* Cover: one dark panel, like the website hero */
.cover{margin-top:8px;padding:clamp(26px,4vw,40px);border-radius:16px;background:var(--night);color:#F3F5FA}
.cover .for{font-size:15px;color:var(--night-soft)}
.cover h1{margin-top:4px;font-size:clamp(26px,3.6vw,36px);line-height:1.15;overflow-wrap:anywhere}
.cover h1 a{color:inherit;text-decoration:none}.cover h1 a:hover{text-decoration:underline;text-underline-offset:6px;text-decoration-thickness:1px}
.verdict{margin-top:14px;font-size:clamp(19px,2.3vw,23px);line-height:1.35}
.cover .meta{margin-top:8px;font-size:15px;color:var(--night-soft)}
.cover .meta code{font-size:13px;padding:1px 6px;border-radius:4px;background:var(--night-2);color:#F3F5FA}
.notice{margin-top:16px;padding:12px 14px;border-radius:8px;background:#3A2E17;color:#F2D49A;font-size:15px}.notice strong{font-weight:600;color:#fff}
/* Overview */
.overview{margin-top:28px;padding:28px 30px;background:#fff;border:1px solid var(--edge);border-radius:12px;box-shadow:0 1px 2px rgba(27,36,64,.05),0 8px 24px rgba(27,36,64,.05)}
.overview-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 24px}
.overview h2{font-size:22px}
.meter{display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px}
.bar{display:flex;width:180px;height:8px;overflow:hidden;border-radius:4px;background:var(--line);gap:2px}
.seg.error{background:var(--red)}.seg.warning{background:var(--amber-bar)}.seg.info{background:var(--blue-bar)}
.meter ul{display:flex;gap:14px;padding:0;list-style:none;font-size:14px;color:var(--soft)}
.meter li{display:inline-flex;align-items:center;gap:6px}
.dot{width:9px;height:9px;border-radius:50%}
.meter .error .dot{background:var(--red)}.meter .warning .dot{background:var(--amber-bar)}.meter .info .dot{background:var(--blue-bar)}
.contents{margin-top:18px;padding:0;list-style:none;border-top:1px solid var(--line)}
.contents li{display:grid;grid-template-columns:72px minmax(0,1fr) auto auto;align-items:center;gap:6px 18px;padding:14px 0;border-bottom:1px solid var(--line)}
.contents li:last-child{border-bottom:0}
.contents li:hover{background:var(--panel)}
.contents a{color:var(--ink);font-weight:600;text-decoration:none}.contents a:hover{color:var(--green);text-decoration:underline;text-underline-offset:4px}
.places{font-size:15px;color:var(--soft)}
.key{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 24px;margin:18px 0 0;padding-top:18px;border-top:1px solid var(--line)}
.key div{display:flex;align-items:baseline;gap:10px}.key dt{flex:none;width:64px}.key dd{margin:0;font-size:14px;line-height:1.45;color:var(--soft)}
.state{font-size:15px;color:var(--soft);text-align:right;min-width:120px}.state.ok{color:var(--green);font-weight:600}.state.bad{color:var(--red-text)}
/* Severity words */
.sev{display:inline-flex;align-items:center;justify-content:center;padding:2px 9px;border-radius:4px;font-size:13px;font-weight:600;line-height:1.5;width:fit-content}
.error .sev{background:var(--red-tint);color:var(--red-text)}.error .sev:before{content:'';width:.72em;height:.72em;margin-right:5px;background:currentColor;-webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M3 3l10 10M13 3L3 13' stroke='black' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat;mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M3 3l10 10M13 3L3 13' stroke='black' stroke-width='3' stroke-linecap='round'/%3E%3C/svg%3E") center/contain no-repeat}
.warning .sev{background:var(--amber-tint);color:var(--amber)}
.info .sev{background:var(--blue-tint);color:var(--blue)}
/* Detail bands */
.band{padding-top:72px}
.band>h2,details.notes>summary{display:flex;align-items:baseline;gap:10px;padding-bottom:12px;border-bottom:2px solid var(--ink);font-size:26px}
.band>h2 .n,details.notes>summary .n{font-size:16px;font-weight:400;color:var(--soft)}
details.notes>summary{cursor:pointer;list-style:none;font-weight:600}
details.notes>summary::-webkit-details-marker{display:none}
details.notes>summary:after{content:'Show';margin-left:auto;font-size:15px;color:var(--green)}
details.notes[open]>summary:after{content:'Hide'}
.group{padding-top:40px;scroll-margin-top:16px}
.group h3{font-size:21px}.group h3 .count{margin-left:6px;font-size:15px;font-weight:400;color:var(--soft)}
.why{margin-top:6px;max-width:64ch;color:var(--soft)}
.group+.group{margin-top:12px}
/* Finding card */
.card{margin-top:20px;background:#fff;border:1px solid var(--edge);border-top:4px solid var(--sevc,var(--blue-bar));border-radius:12px;box-shadow:0 1px 2px rgba(27,36,64,.05),0 8px 24px rgba(27,36,64,.05);scroll-margin-top:16px}
.card.error{--sevc:var(--red)}.card.warning{--sevc:var(--amber-bar)}.card.info{--sevc:var(--blue-bar)}
.card-top{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px;padding:20px 28px 0;font-size:15px;color:var(--soft)}
.tag{padding:1px 9px;border:1px solid #E5C88F;border-radius:4px;background:var(--amber-tint);color:var(--amber);font-size:13px;font-weight:600}
.label{margin-bottom:6px;font-size:14px;font-weight:600;color:var(--soft)}
.evidence{margin:14px 28px 0;padding:20px 24px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
.ev-text{min-width:0}
.sample{font-size:25px;line-height:1.6;overflow-wrap:anywhere}
.sample.code{font-size:15px}.sample.code code{display:inline-block;font-size:14px;padding:4px 10px;border:1px solid var(--line);border-radius:5px;background:#fff;overflow-wrap:anywhere}
.measured{margin-top:8px;color:var(--ink)}
.sequences{display:grid;gap:10px;margin-top:16px;padding:14px 0 0;list-style:none;border-top:1px dashed var(--edge)}
.sequences li{display:flex;align-items:center;gap:14px}
.glyph{flex:none;display:inline-flex;align-items:center;justify-content:center;min-width:64px;height:56px;padding:0 12px;border-radius:8px;background:#fff;border:1px solid #F0C4CA;font-size:28px;line-height:1;color:var(--red-text)}
/* Anek sits Indic letters high in the line box; nudge each script to the optical centre. */
.glyph:lang(hi){padding-top:15px}.glyph:lang(kn){padding-top:8px}
.seq-text{display:flex;flex-direction:column;gap:2px}
.seq-why{font-size:15px;color:var(--ink)}
.sequences code{font-size:12px;color:var(--soft)}
.steps{display:grid;gap:14px;margin:14px 28px 0}
.ai{padding:18px 22px;border:1px solid #CCD8EA;border-radius:10px;background:#EAF0F9}
.ai-head{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:8px 16px;margin-bottom:10px}
.ai-label{font-size:14px;font-weight:600;color:var(--blue)}
.tabs{display:inline-flex;gap:2px;padding:3px;border-radius:8px;background:#D5DFEE}
.tabs label{display:inline-flex;align-items:center;height:30px;padding:0 12px;border-radius:6px;font-size:14px;font-weight:600;line-height:30px;color:var(--blue);cursor:pointer}
.tabs label:hover{color:var(--ink)}.tabs label[lang]{padding-top:5px}
.pane{line-height:1.7}.panes .pane{display:none}.panes .p-en{display:block}
.ai .t-hi:checked~.panes .p-en,.ai .t-kn:checked~.panes .p-en{display:none}
.ai .t-hi:checked~.panes .p-hi,.ai .t-kn:checked~.panes .p-kn{display:block}
.ai .t-en:checked~.ai-head .tab-en,.ai .t-hi:checked~.ai-head .tab-hi,.ai .t-kn:checked~.ai-head .tab-kn{background:#fff;color:var(--ink);box-shadow:0 1px 2px rgba(27,36,64,.16)}
.ai .t-en:focus-visible~.ai-head .tab-en,.ai .t-hi:focus-visible~.ai-head .tab-hi,.ai .t-kn:focus-visible~.ai-head .tab-kn{outline:3px solid var(--green);outline-offset:1px}
.sr-only{position:absolute;width:1px;height:1px;margin:0;opacity:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.repair{padding:18px 22px;border-radius:10px}
.repair-title{font-weight:600}
.repair.ok{border:1px solid #B4D8C4;background:var(--green-tint)}.repair.ok .repair-title{color:var(--green)}
.repair pre{margin-top:12px;padding:12px 14px;border:1px solid #B4D8C4;border-radius:6px;background:#fff;white-space:pre-wrap;overflow-wrap:anywhere}
.repair-note{margin-top:4px;color:var(--ink)}
.attempts{margin-top:14px;font-size:14px;color:var(--soft)}
.attempts summary{width:fit-content;cursor:pointer;font-weight:600;color:var(--green)}
.attempts ol{display:grid;gap:8px;margin-top:10px;padding:0;list-style:none}
.attempts li{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;color:var(--ink)}
.attempts code{padding:1px 6px;border-radius:4px;background:#fff;overflow-wrap:anywhere}
.state .ico,.repair-title .ico,.clean .ico{margin-right:6px}.mark{display:inline-flex}.attempts .ok .mark{color:var(--green)}.attempts .bad .mark{color:var(--red-text)}
.todo{padding:18px 22px;border:1px solid #E8CF9F;border-radius:10px;background:var(--amber-tint)}
.todo-title{margin-bottom:4px;font-weight:600;color:var(--amber)}
.todo-note{margin-top:8px;font-size:15px;color:var(--soft)}
.muted{color:var(--soft)}
.figures{display:grid;gap:14px;margin-top:18px}.figures.pair{grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr))}
.figures figure{display:flex;flex-direction:column;justify-content:space-between;margin:0;padding:16px;border:1px solid var(--edge);border-radius:8px;background:#fff}
.figures figure.after{border-color:#9FCDB4}
/* Natural size: crops are taken at twice the density, so they show at twice the size and stay sharp. */
.figures img{display:block;width:auto;height:auto;max-width:100%;max-height:420px;margin:auto}
figcaption{margin-top:12px;padding-top:10px;border-top:1px solid var(--line);text-align:center;font-size:14px;color:var(--soft)}
.figures .after figcaption{color:var(--green);font-weight:600}
.more{margin:16px 28px 22px;font-size:14px}
.more summary{display:inline-flex;align-items:center;min-height:34px;padding:0 12px;border:1px solid var(--edge);border-radius:6px;background:#fff;cursor:pointer;color:var(--ink);font-weight:600}
.more summary:hover{border-color:#8E9AAE}
.more dl{display:grid;gap:6px;margin-top:12px}.more dl div{display:grid;grid-template-columns:7em minmax(0,1fr);gap:10px}
.more dt{color:var(--soft)}.more dd{margin:0;overflow-wrap:anywhere}
.more pre{max-height:240px;margin-top:10px;padding:12px;overflow:auto;border:1px solid var(--line);border-radius:6px;background:var(--panel);white-space:pre-wrap;overflow-wrap:anywhere}
.clean{margin-top:24px;padding:20px;border-radius:12px;background:var(--green-tint);color:var(--green);font-size:18px}
.foot{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 20px;margin-top:56px;padding:22px 0 40px;border-top:1px solid var(--line);font-size:14px;color:var(--soft)}
@media(max-width:760px){
.card-top{padding:16px 16px 0}.evidence{margin:12px 12px 0;padding:16px}.figures figure{padding:12px}.steps{margin:12px 12px 0}.more{margin:14px 12px 16px}.ai,.repair,.todo{padding:16px}.overview{padding:22px 18px}.band{padding-top:56px}.sample{font-size:23px}
.contents li{grid-template-columns:64px minmax(0,1fr) auto;gap:4px 12px}.contents a{grid-column:2/4}.places{grid-column:2}.state{grid-column:3;text-align:right;min-width:0}
.key{grid-template-columns:minmax(0,1fr)}.more dl div{grid-template-columns:minmax(0,1fr);gap:0}
.top{min-height:76px}.brand{gap:10px}.brand-name{font-size:24px}.brand-sub{font-size:13px;gap:8px}.logo{width:38px;height:38px}.downloads{gap:6px}.downloads a{min-height:40px;padding:0 12px;font-size:14px}.dl-word{display:none}
}
@media(max-width:420px){.downloads a:last-child{display:none}}@media(max-width:360px){.downloads a>span{display:none}.downloads a{padding:0 12px}.downloads .ico{width:18px;height:18px}}
@media print{.panes .pane{display:block!important}.tabs,.attempts summary{display:none}.attempts ol{display:grid!important}.downloads,.more summary{display:none}.cover{background:#fff;color:var(--ink);border:1px solid var(--line)}.cover .for,.cover .meta{color:var(--soft)}.card,.overview{break-inside:avoid;box-shadow:none}details.notes>*{display:block}}
"""


def _file_stem(data):
    """A download name people can recognise later, such as aksharacheck-report-2026-10-30."""
    day=str(data.get("generated_at") or "")[:10]
    return "aksharacheck-report"+("-"+day if re.fullmatch(r"\d{4}-\d{2}-\d{2}",day) else "")


def _download_script(files):
    """Browsers ignore the download attribute on file:// pages and just open the file.
    The report carries its own Markdown and JSON, so the buttons can save a copy
    wherever the report is opened. Without JavaScript the links still open the files."""
    if not files:
        return ""
    payload=json.dumps(files,ensure_ascii=False).replace("<","\\u003c")
    return ('<script type="application/json" id="report-files">'+payload+'</script>'
            '<script>document.querySelectorAll(".downloads a[data-file]").forEach(function(link){'
            'link.addEventListener("click",function(event){try{'
            'var files=JSON.parse(document.getElementById("report-files").textContent);var kind=link.dataset.file;'
            'var blob=new Blob([files[kind]],{type:kind==="json"?"application/json;charset=utf-8":"text/markdown;charset=utf-8"});'
            'var url=URL.createObjectURL(blob);var save=document.createElement("a");save.href=url;'
            'save.download=link.getAttribute("download");document.body.appendChild(save);save.click();save.remove();'
            'setTimeout(function(){URL.revokeObjectURL(url)},2000);event.preventDefault();}catch(error){}});});</script>')


def _language_script():
    """Remember a reader's explanation language and use it in every report card.

    Without JavaScript, independent radio controls still work as before.
    localStorage may be disabled for file:// reports, so storage is optional.
    """
    return ('<script>(function(){'
            'var key="aksharacheck-report-language";'
            'function setLanguage(lang){'
            'if(!/^(en|hi|kn)$/.test(lang))return;'
            'document.querySelectorAll(".ai input.t-"+lang).forEach(function(input){input.checked=true});'
            '}'
            'try{setLanguage(localStorage.getItem(key)||"en")}catch(e){}'
            'document.addEventListener("change",function(event){'
            'var input=event.target;'
            'if(!(input instanceof HTMLInputElement)||input.type!=="radio"||!input.closest(".ai"))return;'
            'var code=input.classList.contains("t-hi")?"hi":input.classList.contains("t-kn")?"kn":'
            'input.classList.contains("t-en")?"en":null;'
            'if(!code)return;'
            'setLanguage(code);'
            'try{localStorage.setItem(key,code)}catch(e){}'
            '});'
            '})();</script>')


def _html_report(data,folder,files=None):
    findings=data.get("findings",[])
    counts=Counter(f.get("severity","info") for f in findings)
    target=data.get("target","")
    stem=_file_stem(data)
    groups=defaultdict(lambda:defaultdict(list))
    for f in findings:
        groups[f.get("severity","info")][f.get("detector","unknown")].append(f)
    bands=[]
    for severity in ORDER:
        if severity not in groups:
            continue
        detectors=sorted(groups[severity].items(),key=lambda pair:(-len(pair[1]),pair[0]))
        ai_ran=bool(_ai_counts(data)[2])
        body="".join(_group(d,items,folder,ai_ran) for d,items in detectors)
        title=SEVERITY[severity][1]
        number='<span class="n">'+str(counts[severity])+'</span>'
        if severity=="info":
            bands.append('<section class="band"><details class="notes"><summary>'+title+' '+number+'</summary>'+body+'</details></section>')
        else:
            bands.append('<section class="band"><h2>'+title+' '+number+'</h2>'+body+'</section>')
    if not bands:
        bands.append('<p class="clean">'+CHECK+'Nothing broke in these checks. That covers this page at these widths, not every page on the site.</p>')

    notices=[]
    ai_state=data.get("ai") or {}
    if ai_state.get("partial"):
        completed=int(ai_state.get("completed_findings") or 0)
        requested=int(ai_state.get("requested_findings") or 0)
        notices.append('<p class="notice"><strong>BharatCode stopped early.</strong> '
                       +esc(f"It finished {completed} of the {requested} findings it was asked about. ")
                       +'Every browser finding below is complete; only some explanations are missing.</p>')
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
        '<link rel="icon" type="image/svg+xml" href="'+REPORT_FAVICON+'">'
        '<title>'+esc(name)+' | AksharaCheck report</title><style>'+CSS+'</style></head><body>'
        '<header class="shell"><div class="top"><span class="brand">'+LOGO+'<span class="brand-text"><span class="brand-name">AksharaCheck</span>'
        '<span class="brand-sub"><span lang="hi">अक्षर जाँच</span><span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span></span></span></span>'
        '<nav class="downloads" aria-label="Download this report"><a href="report.md" download="'+esc(stem)+'.md" data-file="md" aria-label="Download Markdown">'+DOWNLOAD+'<span><span class="dl-word">Download </span>Markdown</span></a>'
        '<a href="report.json" download="'+esc(stem)+'.json" data-file="json" aria-label="Download JSON">'+DOWNLOAD+'<span><span class="dl-word">Download </span>JSON</span></a></nav></div></header>'
        '<main class="shell"><section class="cover" aria-labelledby="report-title"><p class="for">Rendering report</p>'
        '<h1 id="report-title">'+_safe_link(target,name)+'</h1>'
        '<p class="verdict">'+esc(_summary_sentence(counts))+'</p>'
        '<p class="meta">'+esc(checked)+'</p>'+_ai_line(data)+''.join(notices)+'</section>'
        +_overview(groups,counts)+"".join(bands)+'</main>'
        '<footer class="shell"><div class="foot"><span>AksharaCheck measures how Chromium draws the page. It is not a full accessibility audit.</span>'
        '<span><span lang="hi">अक्षर जाँच</span> · <span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span></span></div></footer>'+_download_script(files)+_language_script()+'</body></html>'
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
    if ai.get("partial"):
        lines+=["BharatCode stopped early: it finished "+str(ai.get("completed_findings",0))+" of the "
                +str(ai.get("requested_findings",0))+" findings it was asked about. Every browser finding is complete.",""]
    line=_ai_line(data)
    if line:
        lines+=[re.sub(r"<[^>]+>","",line).replace("&#x27;","'").replace("&amp;","&"),""]
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
            for item in _merged_sequences((f.get("evidence") or {}).get("invalid_sequences") or []):
                lines.append("- "+item["sequence"].strip()+" `"+" ".join(item["codepoints"])+"`: "+PLAIN_REASONS.get(item["reason"].lower(),item["reason"]))
            english=_clean(f.get("ai_explanation"))
            if english and not english.startswith(("BharatCode unavailable","AI unavailable","BharatCode API")):
                lines+=["","BharatCode: "+english]
                for code,label,low,high in (("hi","हिंदी",0x0900,0x097F),("kn","ಕನ್ನಡ",0x0C80,0x0CFF)):
                    if _mostly(f.get("summary_"+code),low,high):
                        lines.append(label+": "+_clean(f["summary_"+code]))
            if fix.get("status")=="verified":
                lines+=["","Fix verified in Chromium at "+str(fix.get("viewport") or f.get("viewport"))+" px:","","```css",_css_text(fix),"```"]
            elif fix.get("status")=="unverified":
                lines+=["","No suggested fix passed: "+str(fix.get("reason","")),"","What to change: "+action]
            else:
                lines+=["","What to change: "+action]
            for t in fix.get("attempts") or []:
                lines.append("- Tried `"+_css_text(t).replace("\n"," ")+"`: "+("passed" if t.get("status")=="verified" else "rejected, "+str(t.get("reason",""))))
            lines+=["","Page: "+str(f.get("url","")),""]
    return "\n".join(lines)


def write_reports(data,dest):
    folder=Path(dest)
    folder.mkdir(parents=True,exist_ok=True)
    # Findings live once, at the top level; pages keep their own counts and screenshots.
    saved={**data,"pages":[{**{k:v for k,v in page.items() if k!="findings"},"finding_count":len(page.get("findings") or [])}
                            if isinstance(page,dict) else page for page in data.get("pages",[])]}
    json_text=json.dumps(saved,indent=2,ensure_ascii=False)
    markdown=_markdown(data)
    (folder/"report.json").write_text(json_text,encoding="utf-8")
    (folder/"report.md").write_text(markdown,encoding="utf-8")
    _copy_fonts(folder)
    (folder/"report.html").write_text(_html_report(data,folder,{"md":markdown,"json":json_text}),encoding="utf-8")
