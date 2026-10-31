"""Deterministic rendering checks. Findings come from browser data, never the model."""
import hashlib
import re
from urllib.parse import urlparse

# Narrow matching avoids mislabeling English content using unrelated Latin fonts.
LEGACY_RE = re.compile(r"(?:kruti\s*dev|krutidev|devlys|chanakya|shree\s*lipi|baraha\s*kan|nudi\s*akshara)", re.I)
DEV = (0x0900, 0x097F)
KAN = (0x0C80, 0x0CFF)
DEV_MATRAS = set(range(0x093E, 0x094D)) | {0x0962, 0x0963}
KAN_MATRAS = set(range(0x0CBE, 0x0CCD)) | {0x0CE2, 0x0CE3}
DEV_CONSONANTS = set(range(0x0915,0x093A)) | set(range(0x0958,0x0960))
KAN_CONSONANTS = set(range(0x0C95,0x0CBA)) | {0x0CDE}
DEV_VOWELS = set(range(0x0904,0x0915)) | {0x0960,0x0961}
KAN_VOWELS = set(range(0x0C85,0x0C95)) | {0x0CE0,0x0CE1}
DEV_SIGNS = {0x093A,0x093B} | set(range(0x093E,0x094D)) | {0x094E,0x094F,0x0955,0x0956,0x0957,0x0962,0x0963}
KAN_SIGNS = (set(range(0x0CBE,0x0CCD))-{0x0CBC}) | {0x0CE2,0x0CE3}
DEV_NUKTA, DEV_VIRAMA = 0x093C,0x094D
KAN_NUKTA, KAN_VIRAMA = 0x0CBC,0x0CCD
DEV_FINAL={0x0901,0x0902,0x0903}
KAN_FINAL={0x0C81,0x0C82,0x0C83}
DEV_LANGUAGES={'hi','mr','ne','sa','kok','mai','bho','doi','brx','sd','awa','mag','new'}
KAN_LANGUAGES={'kn','tcy','kok','sa','btk'}

def script_counts(text):
    return {'devanagari':sum(DEV[0]<=ord(c)<=DEV[1] for c in text),
            'kannada':sum(KAN[0]<=ord(c)<=KAN[1] for c in text)}



def indic_share(text: str, lang: str = "both") -> float:
    nonwhite = [c for c in text if not c.isspace()]
    if not nonwhite:
        return 0
    blocks = [DEV, KAN] if lang == "both" else ([DEV] if lang == "hi" else [KAN])
    return sum(any(lo <= ord(c) <= hi for lo, hi in blocks) for c in nonwhite) / len(nonwhite)


def malformed_clusters(text: str) -> list[dict]:
    """Flag impossible dependent marks without judging spelling or translation."""
    problems=[]
    for i,ch in enumerate(text):
        cp=ord(ch)
        if DEV[0]<=cp<=DEV[1]:
            consonants,vowels,signs,nukta,virama,finals=DEV_CONSONANTS,DEV_VOWELS,DEV_SIGNS,DEV_NUKTA,DEV_VIRAMA,DEV_FINAL
        elif KAN[0]<=cp<=KAN[1]:
            consonants,vowels,signs,nukta,virama,finals=KAN_CONSONANTS,KAN_VOWELS,KAN_SIGNS,KAN_NUKTA,KAN_VIRAMA,KAN_FINAL
        else:
            continue
        prev=ord(text[i-1]) if i else None
        prevprev=ord(text[i-2]) if i>1 else None
        if cp in signs:
            valid=prev in consonants or (prev==nukta and prevprev in consonants)
            reason="dependent vowel sign without a preceding consonant"
        elif cp==nukta:
            valid=prev in consonants
            reason="nukta without a preceding consonant"
        elif cp==virama:
            valid=prev in consonants or (prev==nukta and prevprev in consonants)
            if cp==KAN_VIRAMA and i+1<len(text):
                following=ord(text[i+1])
                # Kannada loanwords such as "ಆ್ಯಪ್" use ಆ + ್ + ಯ.
                # Do not label that sequence a broken character cluster.
                # Unicode also permits vowel + virama + ೞ in Badaga.
                if ((prev in {0x0C85,0x0C86} and following==0x0CAF)
                        or (prev in KAN_VOWELS and following==0x0CDE)):
                    valid=True
            reason="virama without a preceding consonant"
        elif cp in finals:
            valid=prev in consonants or prev in vowels or prev in signs or (prev==nukta and prevprev in consonants)
            reason="final mark without a preceding syllable"
        else:
            continue
        if not valid:
            segment=text[max(0,i-2):i+1]
            problems.append({"position":i,"sequence":segment,"codepoints":[f"U+{ord(c):04X}" for c in segment],"reason":reason})
    return problems[:8]


def finding(page_url, viewport, node, detector, severity, details, *, confidence="measured"):
    identity = "|".join([page_url, str(node.get("selector", "")), detector,
                          hashlib.sha256(node.get("text","")[:180].encode()).hexdigest()[:12],
                          str(details.get("font_url","")) if detector=="font-load-failed" else ""])
    return {"id": hashlib.sha256(identity.encode()).hexdigest()[:12], "url": page_url,
            "viewport": viewport, "viewports":[viewport], "selector": node.get("selector", ""),
            "sample": node.get("text", "")[:180], "detector": detector,
            "severity": severity, "confidence": confidence, "evidence": details,
            "fix": None, "ai_explanation": None}


def run_dom_detectors(page_url, viewport, nodes, lang="both"):
    result = []
    for node in nodes:
        sample = node.get("text", "")
        if len(sample.strip()) < 2:
            continue
        share = indic_share(sample, lang)
        if LEGACY_RE.search(node.get("font", "")) and indic_share(sample) < 0.05 and len(re.findall(r"[A-Za-z]", sample)) >= 5:
            result.append(finding(page_url,viewport,node,"legacy-font", "warning", {"computed_font": node["font"], "note": "Legacy font with Latin-encoded content; verify encoding manually"}, confidence="suspected"))
        if share < 0.15:
            continue
        strange = malformed_clusters(sample)
        if strange:
            result.append(finding(page_url,viewport,node,"broken-cluster","error", {"invalid_sequences":strange}))
        counts=script_counts(sample)
        total=counts["devanagari"]+counts["kannada"]
        effective=(node.get("lang") or "").lower().split("-")[0]
        if total>=6 and min(counts.values())/total>=.15:
            result.append(finding(page_url,viewport,node,"mixed-language","warning",
                                  {"scripts":counts,"effective":effective or "(missing)",
                                   "lang_source":node.get("langSource") or "(unknown)",
                                   "suggestion":"Wrap each language run in a span with its own lang attribute"}))
        elif share>=.45 and len(sample.strip())>=6:
            script="devanagari" if counts["devanagari"]>=counts["kannada"] else "kannada"
            valid=DEV_LANGUAGES if script=="devanagari" else KAN_LANGUAGES
            if effective not in valid:
                result.append(finding(page_url,viewport,node,"wrong-lang","warning",
                                      {"script":script,"effective":effective or "(missing)",
                                       "lang_source":node.get("langSource") or "(unknown)",
                                       "allowed_languages":sorted(valid),"share":round(share,2)}))
        width = float(node.get("clientWidth") or 0)
        scroll = float(node.get("scrollWidth") or 0)
        overflow_x = node.get("overflowX", "visible")
        if viewport <= 430 and width > 10 and scroll > width + 3 and overflow_x not in {"auto", "scroll"} and not node.get("intentionalClamp"):
            result.append(finding(page_url,viewport,node,"mobile-overflow","warning", {"scroll_width":scroll,"client_width":width,"overflow_x":overflow_x}))
        font_size = float(node.get("fontSize") or 0)
        lh = float(node.get("lineHeight") or 0)
        if font_size > 0 and lh and (lh/font_size) < 1.4 and (node.get("lineCount") or 1) > 1:
            result.append(finding(page_url,viewport,node,"tight-line-height","info", {"font_size":font_size,"line_height":lh,"ratio":round(lh/font_size,2)}))
        # ScrollHeight can exceed a 0-1px hidden navigation item even when no text
        # is presented to the reader. Require readable visible geometry and meaningful
        # overflow, but keep the result a suspected issue until visually reviewed.
        visible_height=float(node.get("clientHeight") or 0)
        scroll_height=float(node.get("scrollHeight") or 0)
        visible_width=float(node.get("clientWidth") or 0)
        difference=scroll_height-visible_height
        bounds=node.get("bounds") or {}
        vertical_clipping=(
            node.get("overflowY") in {"hidden","clip"}
            and not node.get("intentionalClamp")
            and visible_width>=12
            and visible_height >= max(12,font_size*.72)
            and difference >= max(7,font_size*.35)
            and not node.get("offscreen",False)
            and not node.get("ariaHidden",False)
            and float(bounds.get("h",visible_height) or 0)>=max(12,font_size*.72)
        )
        if vertical_clipping:
            result.append(finding(page_url,viewport,node,"possible-clipping","warning",
                                  {"scroll_height":scroll_height,"client_height":visible_height,
                                   "overflow_pixels":round(difference,1),
                                   "note":"Potential content clipping. Verify the screenshot before changing CSS."},
                                  confidence="suspected"))
    return result


def failed_font_findings(url, viewport, failures):
    merged={}
    for item in failures:
        if item.get("blocked_by_scanner"):continue
        key=item.get("font_url","")
        if key not in merged or item.get("status"):merged[key]=item
    return [finding(url,viewport,{"selector":"document","text":""},"font-load-failed","error",item) for item in merged.values()]


def font_mismatch_findings(url, viewport, nodes):
    """CDP evidence is informative by default; fallback can be intentional."""
    out=[]
    for n in nodes:
        actual=n.get("platform_fonts") or []
        specified=n.get("font", "").split(",")[0].strip(" '\"\t").lower()
        if not actual or not specified or specified in {"sans-serif","serif","monospace","system-ui","inherit"}:
            continue
        actual_names=[x.get("familyName","").lower() for x in actual if x.get("glyphCount",0)>0]
        if actual_names and all(specified not in name for name in actual_names) and indic_share(n.get("text",""))>.25:
            out.append(finding(url,viewport,n,"font-fallback","info",{"requested":specified,"actual":actual,"note":"Fallback is not always a rendering defect"}))
    return out

def merge_findings(findings):
    """One item per logical issue, with all affected viewports attached."""
    grouped={}
    for f in findings:
        current=grouped.get(f["id"])
        if current is None:
            grouped[f["id"]]=f
            f["viewports"]=list(f.get("viewports") or [f["viewport"]])
            continue
        current["viewports"]=sorted(set(current["viewports"]+f.get("viewports",[f["viewport"]])))
        if f.get("screenshot"):current.setdefault("screenshots",{})[str(f["viewport"])]=f["screenshot"]
        if f.get("element_screenshot"):current.setdefault("element_screenshots",{})[str(f["viewport"])]=f["element_screenshot"]
    return list(grouped.values())
