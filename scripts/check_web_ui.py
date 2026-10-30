"""Browser QA for the AksharaCheck website at nine screen sizes.

Run the frontend first, either the dev server:
    cd web && npm install && npm run dev
or a built copy:
    cd web && npm run build && npx vite preview --port 5173

Then, in another terminal:
    python scripts/check_web_ui.py --url http://127.0.0.1:5173

Screenshots go to output/visual-qa/ and are not committed.
"""
import argparse
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

SIZES = [(320, 640), (360, 780), (390, 844), (430, 932), (768, 1024), (1024, 800), (1280, 720), (1440, 900), (1920, 1080)]
SECTIONS = ["reports", "how", "try", "checks", "run", "faq"]


def check(page, width, height):
    errors = []
    missing = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.on("requestfailed", lambda req: missing.append(req.url.split("?")[0]))
    try:
        page.locator("#hero-title").wait_for(timeout=12000)
    except PlaywrightTimeoutError as exc:
        scripts = page.locator("script[src]").evaluate_all(
            "(nodes) => nodes.map(node => node.getAttribute('src'))"
        )
        raise AssertionError(
            f"{width}px: React homepage did not mount (#hero-title missing). "
            "Rebuild for localhost with 'cd web && npm run build' "
            "(not 'npm run build:pages'). "
            f"Script paths: {scripts}; failed requests: {missing[:3]}; "
            f"JavaScript errors: {errors[:3]}"
        ) from exc
    page.evaluate("document.fonts.ready")
    assert page.title().startswith("AksharaCheck"), "Unexpected browser title"
    for family, weight in (("Anek Latin Variable", 600), ("Anek Devanagari Variable", 400), ("Anek Kannada Variable", 400)):
        assert page.evaluate(f"document.fonts.check('{weight} 16px \"{family}\"')"), f"{family} did not load"
    for section in SECTIONS:
        assert page.locator(f"#{section}").count() == 1, f"{width}px: missing #{section}"

    size = page.evaluate("() => ({root: document.documentElement.scrollWidth, body: document.body.scrollWidth})")
    assert size["root"] <= width + 1 and size["body"] <= width + 1, f"{width}px: sideways scroll {size}"

    frames = page.evaluate("""() => ['.topbar .wrap', '.hero.wrap', '.cta.wrap', '.footer.wrap'].map(s => {
        const r = document.querySelector(s).getBoundingClientRect(); return {s, left: r.left, right: r.right};
    })""")
    first = frames[0]
    assert all(abs(f["left"] - first["left"]) <= 2 and abs(f["right"] - first["right"]) <= 2 for f in frames), (
        f"{width}px: header, hero, closing band and footer do not line up: {frames}")
    assert abs(first["left"] - (width - first["right"])) <= 2, f"{width}px: page is not centred: {first}"

    # Desktop: center the content in the available height and keep the
    # following blue report band below the first visible screen.
    if width > 1024:
        hero = page.evaluate("""() => {
            const box = selector => document.querySelector(selector).getBoundingClientRect();
            const header = box('.topbar'), stage = box('.hero.wrap'),
                  next = box('#reports');
            return {headerBottom: header.bottom, heroTop: stage.top,
                    heroBottom: stage.bottom, heroHeight: stage.height,
                    nextTop: next.top, viewportHeight: innerHeight,
                    copyWidth: box('.hero-copy').width, demoWidth: box('.demo').width,
                    copyTop: box('.hero-copy').top, copyBottom: box('.hero-copy').bottom,
                    demoTop: box('.demo').top, demoBottom: box('.demo').bottom};
        }""")
        assert hero["nextTop"] >= height - 3, (
            f"{width}px: next section is visible beneath the hero: {hero}")
        assert hero["heroHeight"] >= height - hero["headerBottom"] - 3, (
            f"{width}px: hero does not fill the available desktop height: {hero}")
        assert abs(hero["heroTop"] - hero["headerBottom"]) <= 3, (
            f"{width}px: unexpected gap below the header: {hero}")
        assert hero["copyWidth"] > 0 and hero["demoWidth"] > 0
        # Both columns move together slightly above the viewport's
        # mathematical center; their horizontal layout is unchanged.
        expected_lift=max(12,min(height*.025,24))
        hero_center=(hero["heroTop"]+hero["heroBottom"])/2
        content_center=(min(hero["copyTop"],hero["demoTop"])+max(hero["copyBottom"],hero["demoBottom"]))/2
        assert abs((hero_center-content_center)-expected_lift)<6, (
            f"{width}px: hero content isn't optically lifted by {expected_lift:g}px: {hero}")

    # Footer: the English identity sits above the two Indic names.
    footer = page.evaluate("""() => {
        const b = selector => document.querySelector(selector).getBoundingClientRect();
        return {nameBottom: b('.footer-brand strong').bottom,
                hindiTop: b('.footer-brand [lang="hi"]').top,
                kannadaTop: b('.footer-brand [lang="kn"]').top,
                navTop: b('.footer nav').top};
    }""")
    assert footer["hindiTop"] >= footer["nameBottom"] - 2, (
        f"{width}px: footer languages are no longer underneath AksharaCheck: {footer}")
    assert abs(footer["hindiTop"] - footer["kannadaTop"]) < 8, (
        f"{width}px: footer languages are not aligned: {footer}")

    # Button text sits in the vertical middle of its button.
    offsets = page.evaluate("""() => [...document.querySelectorAll('.btn, #site-menu a, .menu-toggle')]
        .filter(b => b.offsetParent !== null)
        .map(b => {
            const box = b.getBoundingClientRect();
            const range = document.createRange(); range.selectNodeContents(b);
            const text = range.getBoundingClientRect();
            return {label: b.textContent.trim(), offset: Math.abs((text.top - box.top) - (box.bottom - text.bottom))};
        })""")
    off_centre = [o for o in offsets if o["offset"] > 3]
    assert not off_centre, f"{width}px: button text off centre: {off_centre}"

    # Header: a readable name, menu options that all match, and nothing overlapping.
    header = page.evaluate("""() => {
        const box = e => e.getBoundingClientRect();
        const brand = box(document.querySelector('.brand'));
        const links = [...document.querySelectorAll('#site-menu a')].filter(a => a.offsetParent !== null);
        const styles = links.map(a => { const c = getComputedStyle(a); return [c.fontSize, c.fontWeight, c.color, Math.round(box(a).height)].join('|'); });
        const toggle = document.querySelector('.menu-toggle');
        const right = links.length ? Math.min(...links.map(a => box(a).left)) : box(toggle).left;
        return {name: parseFloat(getComputedStyle(document.querySelector('.brand-name')).fontSize),
                sub: document.querySelector('.brand-sub').innerText, styles: [...new Set(styles)],
                gap: right - brand.right, links: links.length};
    }""")
    assert header["name"] >= 22, f"{width}px: name too small {header}"
    assert "अक्षर जाँच" in header["sub"] and "ಅಕ್ಷರ ಪರಿಶೀಲನೆ" in header["sub"], f"{width}px: Hindi and Kannada names missing"
    assert len(header["styles"]) <= 1, f"{width}px: menu options do not match {header['styles']}"
    assert header["gap"] >= 16, f"{width}px: name and menu are too close {header}"
    if width > 760:
        assert header["links"] == 6, f"{width}px: menu options missing {header}"

    # Phone menu opens, and closes again when a link is chosen.
    if width <= 760:
        page.locator(".menu-toggle").click()
        assert page.locator("#site-menu").is_visible(), f"{width}px: menu did not open"
        page.locator("#site-menu a[href='#faq']").click()
        page.wait_for_timeout(300)
        assert not page.locator("#site-menu").is_visible(), f"{width}px: menu did not close"

    # The text checker starts broken, switches to the corrected text and back.
    verdict = page.locator(".verdict")
    assert "broken letter" in verdict.inner_text()
    page.get_by_role("button", name="Show the corrected text").click()
    assert "No broken letters" in verdict.inner_text()
    page.get_by_role("button", name="Show the broken example").click()
    assert "broken letter" in verdict.inner_text()
    assert not errors, f"{width}px: script errors {errors}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:5173")
    args = ap.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {"localhost", "127.0.0.1"}:
        ap.error("For safety, visual QA only accepts a locally running frontend")
    shots = Path("output/visual-qa")
    shots.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        import os
        options = {"headless": True}
        if os.getenv("AKSHARA_CHROMIUM_PATH"):
            options["executable_path"] = os.environ["AKSHARA_CHROMIUM_PATH"]
        browser = p.chromium.launch(**options)
        for width, height in SIZES:
            page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1, color_scheme="dark")
            response = page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
            if not response or response.status >= 400:
                raise AssertionError(f"{width}px: the site did not load")
            check(page, width, height)
            # Dark mode on the device must not change the page.
            assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(246, 247, 242)"
            page.wait_for_timeout(3500)
            page.screenshot(path=str(shots / f"site-{width}.png"), full_page=True)
            print(f"{width}px: ok")
            page.close()
        browser.close()
    print(f"All {len(SIZES)} viewports passed.")


if __name__ == "__main__":
    main()
