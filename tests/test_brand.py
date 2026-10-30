"""Protect what matters on the website: content, honesty, accessibility and the light-only design."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PAGE = (WEB / "src" / "main.tsx").read_text(encoding="utf-8")
CSS = (WEB / "src" / "style.css").read_text(encoding="utf-8")
HEAD = (WEB / "index.html").read_text(encoding="utf-8")


def test_head_is_light_only_with_share_preview():
    assert "AksharaCheck | Find the letters your website breaks" in HEAD
    assert 'name="color-scheme" content="only light"' in HEAD
    assert "color-scheme: only light" in CSS
    assert 'href="%BASE_URL%favicon.svg"' in HEAD
    assert 'property="og:image"' in HEAD and (WEB / "public" / "social-preview.png").is_file()
    assert "summary_large_image" in HEAD
    assert "fonts.googleapis" not in HEAD + CSS


def test_sections_and_navigation():
    for anchor in ['id="reports"', 'id="how"', 'id="try"', 'id="checks"', 'id="run"', 'id="faq"']:
        assert anchor in PAGE
    for href in ["#reports", "#how", "#try", "#run", "#faq"]:
        assert f"'{href}'" in PAGE
    assert "https://github.com/ashh-droid/AksharaCheck" in PAGE


def test_bharatcode_is_named_and_honest():
    assert "asks BharatCode to explain it and draft a fix" in PAGE
    assert "The model suggests. The browser decides." in PAGE
    assert "qwen-3.8-27b" in PAGE
    assert "up to three tries" in PAGE
    # The hero example is labelled as an example, not passed off as a real scan.
    assert "Example finding" in PAGE


def test_pages_build_never_calls_a_missing_backend():
    assert "const PAGES_PREVIEW = window.location.hostname.endsWith('.github.io')" in PAGE
    assert "if (PAGES_PREVIEW) return;" in PAGE
    # On Pages the hero offers reports and instructions, never a dead scan box.
    assert "PAGES_PREVIEW ? (" in PAGE and "Run it on your site" in PAGE
    vite = (WEB / "vite.config.ts").read_text(encoding="utf-8")
    package = (WEB / "package.json").read_text(encoding="utf-8")
    assert "mode === 'pages' ? '/AksharaCheck/' : '/'" in vite
    assert '"build:pages"' in package and '"deploy:pages"' in package
    assert (WEB / "public" / ".nojekyll").exists()


def test_recorded_scans_link_only_safe_slugs():
    assert "/^[a-z0-9-]+$/.test(s.slug)" in PAGE
    assert "encodeURIComponent(slug)" in PAGE


def test_self_hosted_fonts():
    package = (WEB / "package.json").read_text(encoding="utf-8")
    for font in ("anek-latin", "anek-devanagari", "anek-kannada"):
        assert "@fontsource-variable/" + font in package
        assert "@fontsource-variable/" + font + "/wght.css" in PAGE


def test_accessibility_basics():
    assert 'className="skip" href="#main"' in PAGE
    assert 'className="brand-sub"' in PAGE and "अक्षर जाँच" in PAGE and "ಅಕ್ಷರ ಪರಿಶೀಲನೆ" in PAGE
    assert 'aria-expanded={open}' in PAGE and 'aria-controls="site-menu"' in PAGE
    assert ":focus-visible" in CSS
    assert "prefers-reduced-motion: reduce" in CSS
    assert 'lang="hi"' in PAGE and 'lang="kn"' in PAGE


def test_no_generated_template_habits():
    assert "text-transform: uppercase" not in CSS
    assert not re.search(r"letter-spacing:\s*\.1", CSS)
    assert not re.search(r"font-weight:\s*(7|8)\d\d", CSS)
    for phrase in ("BETA", "01 /", "Not AI guesses", "Scanner preview only"):
        assert phrase not in PAGE
    assert "—" not in PAGE + HEAD


def test_one_frontend_only():
    assert not (WEB / "src" / "legacy.js").exists()
    assert (WEB / "src" / "letters.ts").is_file()

def test_footer_restoration_and_desktop_hero_viewport():
    css = (WEB / "src" / "style.css").read_text(encoding="utf-8")
    assert "Restore the earlier compact, stacked trilingual footer lockup" in css
    assert "grid-template-columns: 32px max-content max-content" in css
    assert ".footer-brand strong { grid-column: 2 / 4; grid-row: 1; font-size: 22px" in css
    assert "min-height: calc(100svh - 88px)" in css
    assert ".hero h1 { font-size: clamp(46px, 5.55vw, 80px); }" in css
    assert ".demo-glyphs { font-size: clamp(44px, 4.7vw, 70px); }" in css

def test_check_cards_have_extra_breathing_room_before_run_section():
    css = (WEB / "src" / "style.css").read_text(encoding="utf-8")
    assert "padding-top: var(--section); margin-top: clamp(12px, 2vw, 24px);" in css


def test_closing_banner_is_modestly_compact_without_changing_footer_or_hero():
    css = (WEB / "src" / "style.css").read_text(encoding="utf-8")
    assert ".cta { display: flex; flex-wrap: wrap; align-items: center; gap: 18px 23px; margin-top: var(--section); padding: clamp(24px, 3.25vw, 40px);" in css
    assert ".cta .logo { flex: none; width: 44px; height: 44px; }" in css
    assert ".cta h2 { font-size: clamp(23px, 2.5vw, 31px);" in css
    assert ".cta .btn { margin-left: auto; min-height: 44px; padding-inline: 20px; }" in css
    assert "Restore the earlier compact, stacked trilingual footer lockup" in css
    assert "min-height: calc(100svh - 88px)" in css

def test_desktop_hero_content_is_lifted_without_reflow():
    css=(WEB / "src" / "style.css").read_text(encoding="utf-8")
    assert "Slight optical lift:" in css
    assert ".hero > .hero-copy,\n  .hero > .demo" in css
    assert "top: calc(-1 * clamp(12px, 2.5vh, 24px));" in css
    assert "min-height: calc(100svh - 88px)" in css
