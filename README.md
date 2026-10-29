# AksharaCheck · अक्षर चेक · ಅಕ್ಷರ ಪರಿಶೀಲನೆ

**A real-browser detector for Hindi and Kannada text rendering bugs, with AI-proposed CSS fixes rechecked in Chromium.**

> Open a website, find concrete rendering evidence, ask BharatCode to suggest a repair, and only label the repair **verified** after it passes the same deterministic test in a fresh browser. AI never creates findings.

**Stage:** v0.1 working MVP. This is deliberately narrower than the long-term build plan. Not yet a hackathon-final production deployment.

## Quick start (Windows PowerShell)

```powershell
cd aksharacheck
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[test]"
python -m playwright install chromium
aksharacheck scan https://www.india.gov.in/ --lang both --output output
start output\report.html
```

If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -e ".[test]"` and `.venv\Scripts\python.exe -m aksharacheck ...` instead.

For a local demo in **two terminals**:

```powershell
# Terminal 1 - fixture (trusted local testing only)
cd fixtures\toota-akshar
python -m http.server 8765

# Terminal 2 - run scanner
aksharacheck scan http://127.0.0.1:8765/index.html --allow-local --output output
start output\report.html
```

`--allow-local` is a CLI-only fixture option; it is unavailable through the public web API.

## Optional BharatCode AI

Obtain developer API access at https://bharatcode.ai/build; set the key in a **server-side** environment variable. Do not commit or expose it in the browser.

```powershell
$env:BHARATCODE_API_KEY="your_key_here"
aksharacheck scan https://www.india.gov.in/ --ai --output output
```

- Model: `qwen-3.8-27b`.
- Endpoint: `https://bharatcode.ai/api/model/v1/responses`.
- Each prompt contains only the finding record; page text is explicitly untrusted.
- CSS property/value whitelist prevents external URLs and arbitrary CSS from being injected.
- AI explanations/suggestions are not findings; repairs are retested before `verified`.
- With no valid API key, deterministic detection still works. AI calls are **not tested in this distribution**.

## Web app

```powershell
# Terminal 1 (backend)
aksharacheck serve --port 8000

# Terminal 2 (frontend)
cd web
npm install
npm run dev
```

Open http://127.0.0.1:5173. The Vite dev server proxies `/api` to the local backend.

**Fastest no-npm route:** after Python installation, run `aksharacheck serve --port 8000` and open http://127.0.0.1:8000. A standalone, dependency-free interface is included in `web/dist` and served by FastAPI. The React/Vite source in `web/src` is available for further development. If you run `npm run build`, Vite will replace the standalone fallback with its compiled React app. A production deployment needs HTTPS, an external rate limiter, cleanup jobs, persistent job queue, monitored browser resource limits, and a privacy review.

## What is checked?

| Detector | Current output | Notes |
| --- | --- | --- |
| Legacy font (KrutiDev, DevLys, etc.) | Warning | Suspected legacy encoding, not proof of wrong text |
| Actual fallback font (Chrome CDP) | Info | Non-default actual font may be intentional |
| Failed web font request | Error | HTTP failure/request failure; may affect unused font |
| Broken vowel marks | Error | Conservative Unicode patterns; some teaching examples are intentional |
| Text clipping | Warning | Geometry evidence, visual confirmation required |
| Mobile overflow | Warning | Excludes explicitly scrollable or clamped content |
| Wrong/missing `lang` | Warning | Based on actual Unicode script share |
| Tight line spacing | Info | Only multiline content |

Two widths: 390 and 1440 px. JSON, Markdown and HTML reports with screenshots. `--pages 1..10` crawls same-host linked pages. CLI supports `--fail-on warning|error|never` (0 success/no threshold, 1 threshold met, 2 runtime error).

**Known limitations:** Browser coverage is Chromium only; only DOM-rendered text, not PDFs, images, native apps, login pages, spelling/translation, or arbitrary Indic scripts. Results can be false positives. Dynamic sites and consent overlays can cause omissions. Not a complete accessibility audit. Report sample text may contain sensitive information if scanned on a page with private data; restrict use to public pages.

## Tests

```bash
pip install -e '.[test]'
pytest -q tests/test_detectors.py
# Browser integration (requires Chromium)
pip install pytest-asyncio
pytest -q tests/test_browser_integration.py
```

No automatic GitHub Actions workflow is enabled (avoids spending runner minutes). Run checks locally before publishing.

## Repo and hackathon

1. Register at https://bharatcode.ai/hackathon with your BharatCode account.
2. Publish this folder in a **public** GitHub repository, preserving `BharatCode.txt` at the root.
3. Confirm required file content and any submission-specific deadline with the organizers.
4. Submit the **main repository URL**, not a branch/file link.

## Next milestone

Manual verification of the real-site validation sample, screenshot crop comparisons, stronger Unicode syllable validation, multi-page browser evidence, secured production queue, public research methodology, and a 60-second demo. Do not claim 90% detection precision or completed 100-site scans until those are actually measured.

AI-assisted development disclosure: Some initial code and text were drafted with ChatGPT; all security, precision, and compatibility claims require developer review/testing before public deployment.
