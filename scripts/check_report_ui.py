"""Local report visual QA.

Example:
  .venv\\Scripts\\python.exe scripts\\check_report_ui.py output\\ai-demo\\report.html

This script never visits the scanned website. It only opens the local HTML
file in Chromium, checks the layout at five widths and saves screenshots next
to the report in report-visual-qa/.
"""
import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


WIDTHS = [(320, 700), (360, 780), (390, 844), (768, 1024), (1440, 900)]


def check(path):
    source = Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    data_file = source.with_name("report.json")
    findings = json.loads(data_file.read_text(encoding="utf-8")).get("findings", []) if data_file.is_file() else None
    dest = source.parent / "report-visual-qa"
    dest.mkdir(parents=True, exist_ok=True)
    options = {"headless": True}
    if os.getenv("AKSHARA_CHROMIUM_PATH"):
        options["executable_path"] = os.environ["AKSHARA_CHROMIUM_PATH"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**options)
        try:
            for width, height in WIDTHS:
                page = browser.new_page(viewport={"width": width, "height": height}, accept_downloads=True)
                errors = []
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.goto(source.as_uri())
                page.evaluate("document.fonts.ready")
                where = f"{width}px"

                assert page.title().endswith("AksharaCheck report"), f"{where}: report tab title incorrect"
                assert page.locator(".brand-name").inner_text() == "AksharaCheck", f"{where}: brand name missing"
                assert page.locator(".brand-sub span").count() == 2, f"{where}: Hindi and Kannada names missing"
                assert page.locator('.downloads a[href="report.md"]').count() == 1, f"{where}: Markdown download missing"
                assert page.locator('.downloads a[href="report.json"]').count() == 1, f"{where}: JSON download missing"
                assert page.locator(".cover h1").is_visible(), f"{where}: report title not visible"

                cards = page.locator("article.card").count()
                if findings is not None:
                    assert cards == len(findings), f"{where}: {cards} cards for {len(findings)} findings"
                if cards == 0:
                    assert page.locator(".clean").count() == 1, f"{where}: no findings and no clean message"

                # Every overview row must lead to a section that exists.
                for href in page.locator(".contents a").evaluate_all("(links) => links.map(a => a.getAttribute('href'))"):
                    assert page.locator(href).count() == 1, f"{where}: overview link {href} has no target"

                overflow = page.evaluate("({page: document.documentElement.scrollWidth, body: document.body.scrollWidth})")
                assert overflow["page"] <= width + 1 and overflow["body"] <= width + 1, f"{where}: page scrolls sideways {overflow}"

                # Open the notes and every folded detail, so screenshots and image checks cover them.
                page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
                broken = page.evaluate("[...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => i.getAttribute('src'))")
                assert not broken, f"{where}: broken screenshots {broken}"

                # The language switch shows exactly one explanation at a time.
                for ai in page.locator(".ai").all():
                    tabs = ai.locator(".tabs label")
                    for i in range(tabs.count()):
                        tabs.nth(i).click()
                        shown = ai.locator(".pane").evaluate_all(
                            "(panes) => panes.filter(p => getComputedStyle(p).display !== 'none').length")
                        assert shown == 1, f"{where}: language switch shows {shown} explanations"
                    if tabs.count():
                        tabs.first.click()

                # Downloads must save a file even from a file:// report, where browsers ignore "download".
                if width == WIDTHS[-1][0]:
                    for kind in ("md", "json"):
                        with page.expect_download(timeout=5000) as saved:
                            page.locator(f'.downloads a[data-file="{kind}"]').click()
                        name = saved.value.suggested_filename
                        assert name.endswith("." + kind), f"{where}: {kind} download saved as {name}"
                        text = Path(saved.value.path()).read_text(encoding="utf-8")
                        assert text.strip(), f"{where}: {kind} download is empty"
                        if kind == "json":
                            json.loads(text)
                    assert page.url == source.as_uri(), f"{where}: a download button navigated away from the report"
                assert not errors, f"{where}: JavaScript errors {errors}"
                page.screenshot(path=str(dest / f"report-{width}.png"), full_page=True)
                page.close()
                print(f"{where}: ok")
        finally:
            browser.close()
    print(f"All {len(WIDTHS)} widths passed. Screenshots: {dest}")


def main():
    parser = argparse.ArgumentParser(description="Check an AksharaCheck HTML report in Chromium")
    parser.add_argument("report", help="Path to report.html")
    check(parser.parse_args().report)


if __name__ == "__main__":
    main()
