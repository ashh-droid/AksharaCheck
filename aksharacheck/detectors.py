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
DEV_START = set(range(0x093A, 0x094D)) - {0x093C}  # signs require contextual review
KAN_START = set(range(0x0CBE, 0x0CCD))


def indic_share(text: str, lang: str = "both") -> float:
    nonwhite = [c for c in text if not c.isspace()]
    if not nonwhite:
        return 0
    blocks = [DEV, KAN] if lang == "both" else ([DEV] if lang == "hi" else [KAN])
    return sum(any(lo <= ord(c) <= hi for lo, hi in blocks) for c in nonwhite) / len(nonwhite)


def malformed_clusters(text: str) -> list[dict]:
    """Find strong Unicode anomalies; report codepoints so they can be verified."""
    problems = []
    for index, ch in enumerate(text):
        cp = ord(ch)
        mats = DEV_MATRAS if DEV[0] <= cp <= DEV[1] else KAN_MATRAS if KAN[0] <= cp <= KAN[1] else None
        if mats is None:
            continue
        prev = ord(text[index - 1]) if index else None
        if prev in mats and cp in mats and cp not in {0x094D, 0x0CCD} and prev not in {0x094D, 0x0CCD}:
            problems.append({"position": index, "sequence": text[index-1:index+1], "codepoints": [f"U+{prev:04X}", f"U+{cp:04X}"], "reason": "consecutive dependent vowel marks"})
        elif prev is None or text[index - 1].isspace():
            if cp in mats and cp not in {0x094D, 0x0CCD}:
                problems.append({"position": index, "sequence": ch, "codepoints": [f"U+{cp:04X}"], "reason": "dependent vowel mark at word start"})
    return problems[:5]


def finding(page_url, viewport, node, detector, severity, details, *, confidence="measured"):
    identity = "|".join([page_url, str(viewport), str(node.get("selector", "")), detector])
    return {"id": hashlib.sha256(identity.encode()).hexdigest()[:12], "url": page_url,
            "viewport": viewport, "selector": node.get("selector", ""),
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
        if LEGACY_RE.search(node.get("font", "")) and share < 0.05 and len(re.findall(r"[A-Za-z]", sample)) >= 5:
            result.append(finding(page_url,viewport,node,"legacy-font", "warning", {"computed_font": node["font"], "note": "Legacy font with Latin-encoded content; verify encoding manually"}, confidence="suspected"))
        if share < 0.15:
            continue
        strange = malformed_clusters(sample)
        if strange:
            result.append(finding(page_url,viewport,node,"broken-cluster","error", {"invalid_sequences":strange}))
        expected = "hi" if indic_share(sample, "hi") > indic_share(sample, "kn") else "kn"
        effective = (node.get("lang") or "").lower()
        if effective.split("-")[0] != expected and share >= 0.45 and len(sample.strip()) >= 6:
            result.append(finding(page_url,viewport,node,"wrong-lang","warning", {"expected":expected,"effective": effective or "(missing)","share":round(share,2)}))
        width = float(node.get("clientWidth") or 0)
        scroll = float(node.get("scrollWidth") or 0)
        overflow_x = node.get("overflowX", "visible")
        if viewport <= 430 and width > 10 and scroll > width + 3 and overflow_x not in {"auto", "scroll"} and not node.get("intentionalClamp"):
            result.append(finding(page_url,viewport,node,"mobile-overflow","warning", {"scroll_width":scroll,"client_width":width,"overflow_x":overflow_x}))
        font_size = float(node.get("fontSize") or 0)
        lh = float(node.get("lineHeight") or 0)
        if font_size > 0 and lh and (lh/font_size) < 1.4 and (node.get("lineCount") or 1) > 1:
            result.append(finding(page_url,viewport,node,"tight-line-height","info", {"font_size":font_size,"line_height":lh,"ratio":round(lh/font_size,2)}))
        if node.get("overflowY") in {"hidden", "clip"} and float(node.get("scrollHeight") or 0) > float(node.get("clientHeight") or 0) + 3 and not node.get("intentionalClamp"):
            result.append(finding(page_url,viewport,node,"possible-clipping","warning", {"scroll_height":node["scrollHeight"],"client_height":node["clientHeight"],"note":"Geometry suggests clipping; inspect screenshot before confirming"}, confidence="suspected"))
    return result


def failed_font_findings(url, viewport, failures):
    return [finding(url,viewport,{"selector":"document","text":""}, "font-load-failed","error",item) for item in failures]


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
