"""Read-only review of saved AksharaCheck reports. No scanning or model calls.

Usage:
    python scripts/audit_saved_reports.py output/karnataka-varthe/report.json output/prajavani/report.json

Produces one audit-review.json alongside each input. Report data and screenshots
are never overwritten; all warnings are candidate observations, not site verdicts.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from aksharacheck.detectors import malformed_clusters


def font_family_alias_candidate(requested, actual):
    """A naming clue, not proof that glyph fallback did or didn't happen."""
    def normal(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())
    req=normal(requested)
    got=normal(actual)
    if not req or not got:
        return False
    if req==got:
        return True
    # Prajavani's font-face PvTextSemiBold can have an internal family
    # label of "Prajavani Text Semibold". Do not call it a confirmed fallback.
    return req.startswith("pv") and got.startswith("prajavani") and req[2:]==got[len("prajavani"):]


def inspect(path):
    path=Path(path)
    data=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or not isinstance(data.get("findings"),list):
        raise ValueError("Expected saved AksharaCheck report.json with findings")
    findings=data["findings"]
    pages=data.get("pages") or []
    actual=Counter(str(f.get("severity") or "info") for f in findings)
    expected={k:int((data.get("summary") or {}).get(k,0) or 0) for k in ("error","warning","info")}
    types=Counter(str(f.get("detector") or "unknown") for f in findings)
    ids=[f.get("id") for f in findings]
    unique_ids=len(set(ids))
    missing_files=set()
    for p in pages:
        if isinstance(p,dict):
            for key in ("screenshot",):
                if p.get(key) and not (path.parent/str(p[key])).is_file():
                    missing_files.add(str(p[key]))
    for f in findings:
        for key in ("screenshot","element_screenshot"):
            if f.get(key) and not (path.parent/str(f[key])).is_file():
                missing_files.add(str(f[key]))
        for key in ("screenshots","element_screenshots"):
            if isinstance(f.get(key),dict):
                for filename in f[key].values():
                    if filename and not (path.parent/str(filename)).is_file():
                        missing_files.add(str(filename))
        if isinstance(f.get("fix"),dict):
            fix=f["fix"]
            if fix.get("after_screenshot") and not (path.parent/str(fix["after_screenshot"])).is_file():
                missing_files.add(str(fix["after_screenshot"]))
    wrong=[f for f in findings if f.get("detector")=="wrong-lang"]
    effective=Counter(str((f.get("evidence") or {}).get("effective") or "(unknown)") for f in wrong)
    scripts=Counter(str((f.get("evidence") or {}).get("script") or "(unknown)") for f in wrong)
    origins=Counter(str((f.get("evidence") or {}).get("lang_source") or "(not recorded)") for f in wrong)
    lang_geometry=Counter()
    for f in wrong:
        b=f.get("bounds") or {}
        w=float(b.get("w") or 0)
        h=float(b.get("h") or 0)
        x=float(b.get("x") or 0)
        viewport=float(f.get("viewport") or 0)
        if w<2 or h<2:
            lang_geometry["collapsed_or_zero_geometry"]+=1
        elif viewport>0 and (x>=viewport or x+w<=0):
            lang_geometry["offscreen_horizontally"]+=1
        else:
            lang_geometry["potentially_visible"]+=1
    broken=[]
    for f in findings:
        if f.get("detector")!="broken-cluster":
            continue
        sample=str(f.get("sample") or "")
        marks=(f.get("evidence") or {}).get("invalid_sequences") or []
        current=malformed_clusters(sample)
        broken.append({
            "id":f.get("id"),"sample":sample[:180],
            "saved_problem_sequences":[x.get("sequence") for x in marks if isinstance(x,dict)],
            "current_rule_still_flags":bool(current),
            "saved_count":len(marks),"current_count":len(current),
        })
    aliases=[]
    name_pairs=Counter()
    custom_font_mismatch_count=0
    for f in findings:
        if f.get("detector")!="font-fallback":
            continue
        ev=f.get("evidence") or {}
        req=ev.get("requested") or ""
        rendered=[font for font in (ev.get("actual") or [])
                  if isinstance(font,dict) and font.get("glyphCount",0)>0]
        if rendered and all(bool(font.get("isCustomFont")) for font in rendered):
            custom_font_mismatch_count+=1
        for font in rendered:
            got=font.get("familyName") or ""
            name_pairs[(str(req),str(got))]+=1
            if font_family_alias_candidate(req,got):
                aliases.append({"requested":req,"actual":got,"sample":str(f.get("sample") or "")[:100]})
                break
    variants=Counter(tuple(sorted(f.get("viewports") or [f.get("viewport")] )) for f in findings)
    report={
        "source":str(path),"target":data.get("target"),"generated_at":data.get("generated_at"),
        "engine_version":data.get("engine_version"),
        "counts":{"reported":expected,"recounted":dict(actual),
                  "match":all(expected[k]==actual[k] for k in expected)},
        "detectors":dict(types.most_common()),
        "unique_finding_ids":unique_ids,"duplicate_finding_ids":len(ids)-unique_ids,
        "viewport_groups":{",".join(map(str,k)):v for k,v in variants.items()},
        "pages":[{"viewport":p.get("viewport"),"url":p.get("url"),
                  "error":p.get("error"),"finding_count":p.get("finding_count"),
                  "nodes_checked":p.get("nodes_checked")} for p in pages if isinstance(p,dict)],
        "language_tags":{"warning_count":len(wrong),"effective_language_tags":dict(effective),
                         "detected_scripts":dict(scripts),
                         "declaring_elements":dict(origins),
                         "captured_geometry":dict(lang_geometry),
                         "examples":[{"id":f.get("id"),"sample":str(f.get("sample") or "")[:90],
                                      "effective":(f.get("evidence") or {}).get("effective"),
                                      "script":(f.get("evidence") or {}).get("script")}
                                      for f in wrong[:12]]},
        "broken_clusters":broken,
        "possible_custom_font_aliases":{"count":len(aliases),"examples":aliases[:12]},
        "font_name_differences":{
            "custom_font_only_count":custom_font_mismatch_count,
            "pairs":[{"css_family":p[0],"platform_family":p[1],"elements":count}
                     for p,count in name_pairs.most_common(20)],
            "note":"A custom font's CSS alias need not equal its internal platform family name."},
        "missing_screenshot_files":sorted(missing_files)[:100],
        "interpretation":"This is a local evidence review, not a verified website defect count.",
    }
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports",type=Path,nargs="+")
    args=parser.parse_args()
    for path in args.reports:
        try:
            report=inspect(path)
            out=path.parent/"audit-review.json"
            out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print(f"REVIEW: {path}")
            print("  counts:",report["counts"])
            print("  types:",report["detectors"])
            print("  wrong lang tags:",report["language_tags"]["effective_language_tags"])
            print("  language tag origins:",report["language_tags"]["declaring_elements"])
            print("  candidate geometry:",report["language_tags"]["captured_geometry"])
            print("  current-rule broken clusters:",[(b["sample"],b["current_rule_still_flags"]) for b in report["broken_clusters"]])
            print("  custom-font alias candidates:",report["possible_custom_font_aliases"]["count"])
            print("  font-name notes involving custom fonts:",report["font_name_differences"]["custom_font_only_count"])
            print("  missing screenshot files:",len(report["missing_screenshot_files"]))
            print("  saved:",out)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            parser.error(f"{path}: {exc}")


if __name__=="__main__":
    main()
