"""Browser QA for the built AksharaCheck interface.

Run the frontend first:
    cd web
    npm install
    npm run dev

Then, in another terminal:
    python scripts/check_web_ui.py --url http://127.0.0.1:5173

Screenshots are saved under output/visual-qa/ and are not committed.
"""
import argparse
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

SIZES=[(360,780),(390,844),(768,1024),(1024,800),(1440,900),(1920,1080)]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--url",default="http://127.0.0.1:5173")
    args=ap.parse_args()
    parsed=urlparse(args.url)
    if parsed.scheme not in {"http","https"} or parsed.hostname not in {"localhost","127.0.0.1"}:
        ap.error("For safety, visual QA only accepts a locally running frontend")
    shots=Path("output/visual-qa")
    shots.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for width,height in SIZES:
            page=browser.new_page(viewport={"width":width,"height":height},device_scale_factor=1)
            errors=[]
            page.on("pageerror",lambda err:errors.append(str(err)))
            response=page.goto(args.url,wait_until="domcontentloaded",timeout=30000)
            if not response or response.status>=400:
                raise AssertionError(f"{width}px: frontend did not load correctly")
            page.locator("#hero-title").wait_for()
            page.evaluate("document.fonts.ready")
            assert page.title().startswith("AksharaCheck"),"Unexpected browser title"
            assert page.locator(".brand-name").inner_text()=="AksharaCheck"
            assert "अक्षर जाँच" in page.locator(".brand-subtitle").inner_text()
            assert "ಅಕ್ಷರ ಪರಿಶೀಲನೆ" in page.locator(".brand-subtitle").inner_text()
            assert page.get_by_text("390 px example").count()==1
            assert page.evaluate("document.fonts.check('600 16px \"Anek Latin Variable\"')"),"Locally hosted Anek Latin font not loaded"
            assert page.evaluate("document.fonts.check('400 16px \"Anek Devanagari Variable\"')"),"Locally hosted Hindi font not loaded"
            assert page.evaluate("document.fonts.check('400 16px \"Anek Kannada Variable\"')"),"Locally hosted Kannada font not loaded"
            assert page.locator("a[href='#faq']").count()==1
            assert page.locator("a[href='#checks']").count()==1
            for section in ["try","checks","report","faq"]:
                assert page.locator(f"#{section}").count()==1,f"{width}px: missing #{section}"
            overflow=page.evaluate(
                "()=>({body:document.body.scrollWidth,root:document.documentElement.scrollWidth,viewport:innerWidth})"
            )
            assert overflow["root"]<=width+2 and overflow["body"]<=width+2,(
                f"{width}px: horizontal overflow: {overflow}"
            )
            geometry=page.evaluate("""() => {
                const r=s=>document.querySelector(s).getBoundingClientRect();
                const center=o=>(o.top+o.bottom)/2;
                const wrap=r('.hero.wrap'),cta=r('.bottom-cta'),button=r('.bottom-cta a');
                const badge=r('.sample-report-top .sample-error'),title=r('.sample-report-top strong');
                return {left:wrap.left,right:innerWidth-wrap.right,
                        brand:r('.brand').width,
                        ctaOffset:Math.abs(center(cta)-center(button)),
                        badgeOffset:Math.abs(center(badge)-center(title))};
            }""")
            assert abs(geometry["left"]-geometry["right"])<3,(
                f"{width}px: page frame is not centered: {geometry}"
            )
            alignment=page.evaluate("""() => {
                const selectors=['.topbar .wrap','.hero.wrap','.bottom-cta.wrap','.footer.wrap'];
                return selectors.map(s=>({selector:s,left:document.querySelector(s).getBoundingClientRect().left,
                    right:document.querySelector(s).getBoundingClientRect().right}));
            }""")
            assert all(abs(r["left"]-alignment[0]["left"])<=3 and
                       abs(r["right"]-alignment[0]["right"])<=3
                       for r in alignment),f"{width}px: header, hero, CTA, footer disagree on alignment: {alignment}"
            if width>=1440:
                desktop=page.evaluate("""() => ({
                    frame:document.querySelector('.hero.wrap').getBoundingClientRect().width,
                    brand:parseFloat(getComputedStyle(document.querySelector('.brand-name')).fontSize),
                    footerBrand:parseFloat(getComputedStyle(document.querySelector('.footer-brand strong')).fontSize),
                    sheet:document.querySelector('.hero-sheet').getBoundingClientRect().width
                })""")
                ideal=min(width-2*min(48,max(20,width*.03)),1420)
                assert abs(desktop["frame"]-ideal)<5,f"{width}px: editorial frame not centered at intended width: {desktop}"
                assert desktop["brand"]>=27,f"{width}px: company name too small: {desktop}"
                assert desktop["footerBrand"]>=22,f"{width}px: footer name too small: {desktop}"
                assert desktop["sheet"]>=500,f"{width}px: hero art too narrow: {desktop}"
            assert geometry["brand"]>(150 if width<=480 else 180),f"{width}px: brand lockup too small"
            if width>720:
                assert geometry["ctaOffset"]<18,f"{width}px: closing action not vertically centered"
                assert geometry["badgeOffset"]<10,f"{width}px: sample status badge not aligned"

            # The editor starts with visible issues. The control toggles to a clean example.
            textarea=page.get_by_role("textbox",name="Hindi or Kannada text to check")
            assert "सूचना" in textarea.input_value()
            page.get_by_role("button",name="Show a clean example").click()
            assert "किताब" in textarea.input_value()
            assert "Clean example loaded" in page.locator(".sample-feedback").inner_text()
            page.get_by_role("button",name="Show a broken example").click()
            assert "सूचना" in textarea.input_value()
            assert "Broken example loaded" in page.locator(".sample-feedback").inner_text()
            textarea.fill("कन्नड")
            assert textarea.input_value()=="कन्नड"
            page.get_by_role("button",name="Show a broken example").click()
            assert "सूचना" in textarea.input_value()
            page.get_by_role("button",name="Replay example").click()
            assert page.locator(".hero-sheet").count()==1
            page.get_by_role("button",name="hi.wikipedia.org").click()
            assert page.locator("#url").input_value()=="https://hi.wikipedia.org/"
            page.locator("#url").fill("")
            assert page.locator(".sample-report-top .sample-error").is_visible()
            assert page.locator(".bottom-cta a").is_visible()
            if width<=720:
                menu=page.get_by_role("button",name="Open navigation")
                assert menu.is_visible()
                menu.click()
                assert page.get_by_role("navigation",name="Main navigation").get_by_role("link",name="What it checks").is_visible()
                page.get_by_role("navigation",name="Main navigation").get_by_role("link",name="What it checks").click()
                assert page.get_by_role("button",name="Open navigation").get_attribute("aria-expanded")=="false"
            page.screenshot(path=str(shots/f"aksharacheck-{width}.png"),full_page=True,animations="disabled")
            assert not errors,f"{width}px JavaScript errors: {errors}"
            print(f"PASS {width} x {height}: layout, navigation, controls, content, and screenshot")
            page.close()
        browser.close()
    print(f"All six viewports passed. Screenshots: {shots.resolve()}")

if __name__=="__main__":
    main()
