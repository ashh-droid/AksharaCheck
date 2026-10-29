"""Publish a *reviewed* browser scan as a static GitHub Pages example.

Requires a local AksharaCheck report.json + report.html and accompanying
PNG files. No network access or model calls occur. The operator must inspect
the report for private data before setting --reviewed-public-content.

Example from repo root:
  python scripts/publish_recorded_scan.py output/hi-wikipedia-v2 \
      --slug hindi-wikipedia --title "Hindi Wikipedia" --reviewed-public-content
Then commit web/public/samples and rebuild the frontend for Pages.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "web" / "public" / "samples"
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ASSETS = {"report.json", "report.html", "report.md"}


def public_url(value: str) -> bool:
    try:
        u = urlsplit(value)
        if u.scheme not in {"http", "https"} or not u.hostname or u.username or u.password:
            return False
        host = u.hostname.lower().rstrip(".")
        if host in {"localhost"} or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return "." in host
    except ValueError:
        return False


def copy_scan(folder: Path, slug: str, title: str, reviewed: bool):
    if not reviewed:
        raise ValueError("Review the report for sensitive text and pass --reviewed-public-content.")
    if not SAFE_SLUG.fullmatch(slug):
        raise ValueError("Slug must use lowercase words separated by hyphens.")
    data_path = folder / "report.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not public_url(data.get("target", "")):
        raise ValueError("Only reports for public web pages can be published.")
    if not isinstance(data.get("findings"), list) or not data.get("pages"):
        raise ValueError("Incomplete or invalid scan report.")
    if any("error" in page for page in data["pages"]):
        raise ValueError("The browser scan is incomplete; choose a complete report.")
    missing = [file for file in ASSETS if not (folder / file).is_file()]
    if missing:
        raise ValueError("Missing report files: " + ", ".join(sorted(missing)))
    files = set(ASSETS)
    for page in data["pages"]:
        shot = page.get("screenshot")
        if shot:
            files.add(shot)
    for item in data["findings"]:
        for field in ("screenshot", "element_screenshot"):
            shot = item.get(field)
            if shot:
                files.add(shot)
        for field in ("screenshots", "element_screenshots"):
            shots = item.get(field) or {}
            if isinstance(shots, dict):
                files.update(shots.values())
    for name in files:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Unexpected report asset path.")
        if name not in ASSETS and not (name.startswith(("page-", "element-")) and name.endswith(".png")):
            raise ValueError("Invalid screenshot filename: " + name)
        if not (folder / name).is_file():
            raise ValueError("Required evidence file is missing: " + name)
    target = SAMPLES / slug
    if target.exists():
        raise ValueError("Sample already exists; use a different slug to avoid accidental overwrite.")
    target.mkdir(parents=True)
    for name in files:
        shutil.copy2(folder / name, target / name)
    catalog = SAMPLES / "catalog.json"
    collection = json.loads(catalog.read_text(encoding="utf-8")) if catalog.is_file() else {"scans": []}
    created = str(data.get("generated_at") or datetime.now(timezone.utc).isoformat(timespec="seconds"))
    collection["scans"].append({
        "slug": slug,
        "title": title.strip(),
        "target": data["target"],
        "scanned_at": created,
        "counts": data.get("summary", {}),
    })
    catalog.write_text(json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Recorded sample ready:", target)
    print("Review the copied files before committing or deploying.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--reviewed-public-content", action="store_true")
    args = parser.parse_args()
    try:
        copy_scan(args.folder, args.slug, args.title, args.reviewed_public_content)
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
