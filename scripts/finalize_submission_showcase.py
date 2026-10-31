"""Finalize the reviewed three-report hackathon gallery without API calls.

Run from the repository root:
    .venv\\Scripts\\python.exe scripts\\finalize_submission_showcase.py

Requires the complete local output/karnataka-varthe-final/ report. The
pre-existing Hindi Wikipedia files remain archived, but its gallery entry and
README showcase link are replaced with the reviewed Kannada scan.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from publish_recorded_scan import ROOT, SAMPLES, copy_scan

SLUG = "karnataka-varthe-kannada"
TITLE = "Karnataka Varthe (Kannada)"
TARGET = "https://varthe.karnataka.gov.in/"
ENGINE = "2026-10-31-precision"
NOTE = (
    "72 of these share one cause: the page's <html> tag says English "
    "(lang=\"en\"), so one change fixes them. One possible overflow still "
    "needs a visual check."
)
BASE = "https://ashh-droid.github.io/AksharaCheck/samples/"
NEW_LINK = f"{BASE}{SLUG}/report.html"
WIKI_LINK = BASE + "hindi-wikipedia/report.html"
DD_LINK = BASE + "dd-news-hindi/report.html"


def validate(data: dict, folder: Path) -> None:
    """Require the exact, complete and independently reviewed source capture."""
    if not isinstance(data, dict) or data.get("target") != TARGET:
        raise ValueError("Expected the Karnataka Varthe homepage report.")
    if data.get("engine_version") != ENGINE:
        raise ValueError("Use the corrected 2026-10-31-precision browser scan.")
    if (data.get("ai") or {}).get("calls") or any(
        f.get("ai_explanation") for f in data.get("findings", [])
    ):
        raise ValueError("This public browser-only report must not claim BharatCode calls.")
    pages = data.get("pages") or []
    if {p.get("viewport") for p in pages} != {390, 1440}:
        raise ValueError("Both 390px and 1440px Chromium pages are required.")
    if any(p.get("error") or not (folder / str(p.get("screenshot") or "")).is_file()
           for p in pages):
        raise ValueError("Missing or incomplete page screenshots.")
    findings = data.get("findings") or []
    if len(findings) != 86:
        raise ValueError("Expected the previously reviewed 86 findings. Review changed scans separately.")
    counts = Counter(f.get("detector") for f in findings)
    if counts != {"wrong-lang": 72, "mobile-overflow": 1, "font-fallback": 13}:
        raise ValueError(f"Finding types changed: {dict(counts)}")
    wrong = [f for f in findings if f.get("detector") == "wrong-lang"]
    if any((f.get("evidence") or {}).get("lang_source") != "html"
           or (f.get("evidence") or {}).get("effective") != "en"
           or (f.get("evidence") or {}).get("script") != "kannada"
           for f in wrong):
        raise ValueError("Language-tag inheritance no longer matches the audited evidence.")
    expected = {"error": 0, "warning": 73, "info": 13}
    if data.get("summary") != expected:
        raise ValueError(f"Report totals differ from the audited record: {data.get('summary')}")
    if len(set(f.get("id") for f in findings)) != len(findings):
        raise ValueError("Duplicate finding IDs")
    for filename in ("report.html", "report.json", "report.md"):
        if not (folder / filename).is_file():
            raise ValueError(f"Missing {filename}")


def replace_readme(s: str) -> str:
    old = f"[Hindi Wikipedia report]({WIKI_LINK})"
    new = f"[Karnataka Varthe (Kannada) report]({NEW_LINK})"
    # Keep Wikipedia's archived report link once the Kannada showcase exists.
    # Only replace the old navigation link during the first migration.
    if NEW_LINK not in s and old in s:
        s = s.replace(old, new, 1)
    elif NEW_LINK not in s:
        raise ValueError("Could not find the README showcase link.")

    old_row = (
        f"| [Hindi Wikipedia]({WIKI_LINK}), 31 Oct 2026 | "
        "0 problems, 0 to check, 3 notes (font fallback and line spacing observations). "
        "Browser checks only, no model calls. |"
    )
    new_rows = (
        f"| [Karnataka Varthe (Kannada)]({NEW_LINK}), 31 Oct 2026 | "
        "0 errors; 72 Kannada text observations inherit `lang=en` "
        "from one HTML ancestor. One possible mobile-overflow warning remains unverified; "
        "13 font-name observations are informational. Browser-only scan, not a site-wide audit. |\n"
        f"| [DD News (Hindi)]({DD_LINK}), 31 Oct 2026 | "
        "0 findings at the two tested widths. Chromium sampled 162 phone and "
        "213 desktop text elements; the report includes both page screenshots. "
        "Browser-only scan, no AI calls. |"
    )
    if old_row in s:
        s = s.replace(old_row, new_rows, 1)
    elif (f"| [Karnataka Varthe (Kannada)]({NEW_LINK}), 31 Oct 2026 |" not in s
          or f"| [DD News (Hindi)]({DD_LINK}), 31 Oct 2026 |" not in s):
        raise ValueError("Could not find the reviewed Kannada/Hindi results rows.")

    s = s.replace(
        "Both reports are published exactly as AksharaCheck wrote them. Open them "
        "to see the screenshots, the character codes, every repair attempt "
        "and the Markdown and JSON downloads.",
        "These are dated Chromium snapshots. The BharatCode test fixture shows "
        "AI explanations and verified repairs; public-site reports contain "
        "browser-only evidence, not BharatCode-generated findings. "
        "The earlier Hindi Wikipedia report remains available at its archived link.",
    )
    s = s.replace(
        "| `tests/` | 138 tests, including real-browser checks of the website and reports |",
        "| `tests/` | Automated unit and real-browser checks of the website and reports |",
    )
    return s


def finalize(source: Path) -> None:
    source = source.resolve()
    data = json.loads((source / "report.json").read_text(encoding="utf-8"))
    validate(data, source)

    public_folder = SAMPLES / SLUG
    catalog = SAMPLES / "catalog.json"
    if public_folder.exists():
        published = public_folder / "report.json"
        if not published.is_file() or published.read_bytes() != (source / "report.json").read_bytes():
            raise ValueError("A different report is already published under the Kannada slug.")
    else:
        copy_scan(source, SLUG, TITLE, reviewed=True)

    collection = json.loads(catalog.read_text(encoding="utf-8"))
    entries = {row["slug"]: row for row in collection.get("scans", [])}
    for required in ("akshara-fixture-demo", SLUG, "dd-news-hindi"):
        if required not in entries:
            raise ValueError(f"Missing required recorded report: {required}")
    entries[SLUG]["review_note"] = NOTE
    collection["scans"] = [
        entries["akshara-fixture-demo"],
        entries[SLUG],
        entries["dd-news-hindi"],
    ] + [
        row for row in collection["scans"]
        if row["slug"] not in {"akshara-fixture-demo", SLUG, "dd-news-hindi", "hindi-wikipedia"}
    ]

    readme = ROOT / "README.md"
    revised = replace_readme(readme.read_text(encoding="utf-8"))
    readme.write_text(revised, encoding="utf-8")
    catalog.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("PASS: Reviewed Kannada evidence and updated the three-card gallery.")
    print("  72 Kannada text observations share the HTML English language tag.")
    print("  The 1 mobile-overflow warning remains unverified, not a confirmed defect.")
    print("  The old Wikipedia report files were preserved.")
    print("  No BharatCode calls, no changes to historical reports.")
    print("NEXT: Inspect, test, git add README.md web/public/samples, commit, push and deploy Pages.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "output" / "karnataka-varthe-final")
    args = parser.parse_args()
    try:
        finalize(args.source)
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
