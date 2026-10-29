# AksharaCheck · अक्षर चेक · ಅಕ್ಷರ ಪರಿಶೀಲನೆ

**Find the letters your website breaks. A real-browser checker for Hindi and Kannada rendering, with evidence-backed repair suggestions.**

> Open a website, find concrete rendering evidence, ask BharatCode to suggest a repair, and only label the repair **verified** after it passes the same deterministic test in a fresh browser. AI never creates findings.

**Status:** Functional MVP undergoing public-demo validation. Browser detection and AI repairs have different verification states; the public report will use only measured findings.

## Website experience

The frontend follows the **Attested school-copybook** identity: paper ground, ruled blue lines, correction red, verified green, fountain-pen blue-black and the circular AksharaCheck mark. The masthead, browser tab title and SVG favicon use this identity.

The React interface includes the URL scanner, a browser-only Hindi/Kannada typing check, four visual detector explanations, a sample evidence card, common questions, and live scan reports with page screenshots and repair status. The typing check runs locally in the visitor's browser. Actual website scans use FastAPI and Playwright.

The new page is authored in `web/src/main.tsx` and `web/src/style.css`. The final Vite build is served by FastAPI from `web/dist`. No second web implementation is required.

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
- With no valid API key, deterministic detection still works. The live BharatCode request and structured-output compatibility still require a server-side integration test with a valid key.

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

**One frontend:** React/Vite is the only web UI. The `web/dist` directory is generated locally and is not committed. To serve the compiled UI from FastAPI, build it first:

```powershell
cd web
npm install
npm run build
cd ..
.venv\Scripts\python.exe -m aksharacheck serve --port 8000
```

Then visit http://127.0.0.1:8000. The CLI works without npm; the graphical interface does not. Do not deploy the browser scanner publicly without process isolation, outbound private-network blocking and an external rate limiter.

## Frontend and responsive QA

Start Vite from the repository's `web` folder:

```powershell
cd web
npm install
npm run build
npm run dev
```

In a second terminal, at the repository root:

```powershell
.venv\Scripts\python.exe scripts/check_web_ui.py --url http://127.0.0.1:5173
```

The check visits 360, 390, 768, 1024, 1440 and 1920 pixel widths and checks
the browser header and subtitle, navigation (including the phone menu), the
sample-text button, replay button, evidence example, horizontal overflow and
uncaught JavaScript errors. Full-page screenshots are written to
`output/visual-qa/`.

This is a visual smoke test, not a substitute for manual screenshot review or
a real FastAPI scanner run. Do not claim a passed build until these commands
have been executed successfully on the current branch.

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
pytest -q tests/test_detectors.py tests/test_regressions.py
# Browser integration (requires Chromium)
pip install pytest-asyncio
pytest -q tests/test_browser_integration.py
```

Also run `cd web && npm install && npm run build` and test a complete Chromium scan. CI is not enabled while the repository is private; do not merge a PR without these checks.

## Repo and hackathon

1. Register at https://bharatcode.ai/hackathon with your BharatCode account.
2. Publish this folder in a **public** GitHub repository, preserving `BharatCode.txt` at the root.
3. Confirm required file content and any submission-specific deadline with the organizers.
4. Submit the **main repository URL**, not a branch/file link.

## Next milestone

Run the updated golden tests, test the React build and a live BharatCode API call, validate on a small real-site sample, then deploy and record a 60-second demonstration. Do not claim 90% detection precision or completed 100-site scans until those are actually measured.

**Development disclosure:** ChatGPT assisted with architecture, implementation, testing plans and interface design. The team independently reviewed the original MVP and identified detector and verifier defects that are being corrected in PR #1. A real browser and BharatCode API run is required before calling this release fully validated.
