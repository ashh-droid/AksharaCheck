"""Local report visual QA.

Example:
  .venv\Scripts\python.exe scripts\check_report_ui.py output\hi-wikipedia\report.html

This script never visits the scanned website. It only opens the local HTML
file in Chromium and saves screenshots at four responsive widths.
"""
import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


WIDTHS = [(360, 780), (390, 844), (768, 1024), (1440, 900)]


def check(path):
    source=Path(path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    dest=source.parent/"report-visual-qa"
    dest.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            for width,height in WIDTHS:
                page=browser.new_page(viewport={"width":width,"height":height})
                errors=[]
                page.on("pageerror",lambda error: errors.append(str(error)))
                response=page.goto(source.as_uri(),wait_until="load")
                page.locator("h1").wait_for()
                assert page.title().startswith("AksharaCheck"),"Report tab title incorrect"
                assert page.locator(".brand-name").inner_text()=="AksharaCheck"
                assert page.locator(".score-item").count()==3
                assert page.get_by_role("link",name="JSON").get_attribute("href")=="report.json"
                assert page.get_by_role("link",name="Markdown").get_attribute("href")=="report.md"
                assert page.locator(".brand-sub span").count()==2
                assert page.locator(".finding-row").count()>=0
                assert page.locator(".hero h1").is_visible()
                layout=page.evaluate("""() => {
                    const box=s=>document.querySelector(s).getBoundingClientRect();
                    const hero=box('.hero'),title=box('.hero-copy'),
                          summary=box('.score-panel'),header=box('.topbar');
                    return {heroHeight:hero.height,titleRight:title.right,
                            titleBottom:title.bottom,summaryLeft:summary.left,
                            summaryTop:summary.top,summaryBottom:summary.bottom,
                            headerBottom:header.bottom,heroTop:hero.top};
                }""")
                assert abs(layout["heroTop"]-layout["headerBottom"]) < 3,(
                    f"{width}px: gap between header and report overview: {layout}"
                )
                if width > 800:
                    assert layout["titleRight"] + 16 <= layout["summaryLeft"],(
                        f"{width}px: report heading and summary overlap: {layout}"
                    )
                    assert layout["heroHeight"] < 410,(
                        f"{width}px: report overview uses excessive vertical space: {layout}"
                    )
                else:
                    assert layout["summaryTop"] >= layout["titleBottom"] - 3,(
                        f"{width}px: stacked report summary overlaps heading: {layout}"
                    )
                assert page.locator(".issue-group").count()>=1 or page.locator(".empty").count()==1
                overflow=page.evaluate("""() => ({
                    page: document.documentElement.scrollWidth,
                    body: document.body.scrollWidth,
                    viewport: window.innerWidth
                })""")
                assert overflow["page"]<=width+2 and overflow["body"]<=width+2,(
                    f"{width}px: horizontal overflow {overflow}"
                )
                groups=page.locator("details.issue-group")
                if groups.count():
                    current=groups.first
                    summary=current.locator(":scope > summary")
                    if current.get_attribute("open") is None:
                        summary.click()
                    assert current.get_attribute("open") is not None
                    row=current.locator(".finding-row").first
                    detail=row.locator("details.technical")
                    detail.locator("summary").click()
                    assert detail.get_attribute("open") is not None
                    assert row.locator(".technical-body").is_visible()
                    broken=page.evaluate("""() => [...document.querySelectorAll('.capture img')]
                        .filter(image => image.complete && image.naturalWidth === 0)
                        .map(image => image.getAttribute('src'))""")
                    assert not broken,f"{width}px: broken screenshot previews {broken}"
                    detail.locator("summary").click()
                assert not errors,f"{width}px JavaScript errors: {errors}"
                page.screenshot(path=str(dest/f"report-{width}px.png"),full_page=True,animations="disabled")
                print(f"PASS {width} x {height}: responsive layout, details and evidence controls")
                page.close()
        finally:
            browser.close()
    print("Screenshots:",dest)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("report",help="Path to local report.html")
    args=parser.parse_args()
    check(args.report)
