# AksharaCheck · अक्षर जाँच · ಅಕ್ಷರ ಪರಿಶೀಲನೆ

**Find the letters your website breaks. A real-browser checker for Hindi and Kannada rendering, with evidence-backed repair suggestions.**

> Open a website, find concrete rendering evidence, ask BharatCode to suggest a repair, and only label the repair **verified** after it passes the same deterministic test in a fresh browser. AI never creates findings.

**Status (31 October 2026):** The controlled nine-finding BharatCode demo passed on Windows: 9/9 actionable findings received explanations, and Chromium independently verified 4 proposed repairs. A separately recorded scan of Hindi Wikipedia returned 0 errors, 0 warnings and 3 informational notes. The public Pages preview hosts these reviewed *recordings* and a local-in-browser text checker; it does not run the Python/Chromium scanning backend.

## Try AksharaCheck

[Try the Hindi/Kannada text checker (GitHub Pages)](https://ashh-droid.github.io/AksharaCheck/) · [Source code](https://github.com/ashh-droid/AksharaCheck) · [Submission instructions](https://bharatcode.ai/hackathon)

The static Pages preview lets visitors check Hindi/Kannada text in their own browser. **Full website scans run locally with Python + Chromium**; GitHub Pages alone cannot run the scanner or store a BharatCode API key. Two reviewed reports are now committed and deployed to the separate `gh-pages` branch. The local fixture is explicitly labelled as a controlled demo, not an audit of a public website.

### See the recorded evidence

- [BharatCode end-to-end controlled demo report](https://ashh-droid.github.io/AksharaCheck/samples/akshara-fixture-demo/report.html): 3 errors, 6 warnings, 2 notes. BharatCode explained all 9 actionable findings in English, Hindi and Kannada; Chromium verified 4 repairs. Six new model calls completed and three earlier explanations were reused and their eligible repairs rechecked. **This is a deliberately broken local test page, not a real website.**
- [Independent Hindi Wikipedia scan](https://ashh-droid.github.io/AksharaCheck/samples/hindi-wikipedia/report.html): measured on 31 October 2026 at 390 px and 1440 px; 0 errors, 0 warnings and 3 informational notes. **No BharatCode model call was made for this scan.** Notes do not establish that Wikipedia is broken.

These are recorded results, not a continuously running public crawler. Open the full HTML reports for their screenshots, evidence and provenance. A short recording of the actual terminal and Chromium verification run is still to be added.

### How BharatCode is used

1. **Chromium finds evidence.** AksharaCheck measures real rendered text at phone and desktop widths. Deterministic checks identify language tags, broken character clusters, overflow and other text-rendering problems; BharatCode never invents the findings.
2. **BharatCode explains and proposes.** The `qwen-3.8-27b` Responses API produces structured English explanations, Hindi and Kannada summaries, and a restricted CSS or language-attribute proposal. Site content is treated as untrusted.
3. **Chromium judges the repair.** A fresh browser checks the proposed change against the original problem and catches regressions such as hidden, shrunken or displaced text. Only a passing result is marked **verified**. Failed model streams and rejected suggestions are disclosed, not hidden.

### Three steps to run a real scan on Windows

```cmd
git clone https://github.com/ashh-droid/AksharaCheck.git
cd AksharaCheck
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m playwright install chromium
.venv\Scripts\python.exe -m aksharacheck scan https://hi.wikipedia.org/ --lang both --output output\first-scan
start output\first-scan\report.html
```

The browser scan does not require an AI key. For the optional real BharatCode demo, run `.venv\Scripts\python.exe scripts\run_ai_demo.py --max-findings 9`; enter your key only at the hidden prompt. The test fixture deliberately contains nine actionable findings. The demo saves and rechecks progress so previous verified explanations are not requested again unless the underlying evidence changes.

For automated checks, `.venv\Scripts\python.exe -m aksharacheck scan https://hi.wikipedia.org/ --fail-on error --output output\ci-scan` exits unsuccessfully when an error-level finding is detected. These results are scoped rendering checks, **not** a comprehensive accessibility certification.

For the hackathon, the reviewed recorded scans are linked above. A report-cover screenshot and a brief unedited capture of the live BharatCode-to-Chromium demonstration should be added when available; do not invent screenshots or claim model calls that did not occur.

## Submission evidence and recording

The [submission guide](docs/SUBMISSION_GUIDE.md) includes the verified BharatCode Build League requirements, a 2–3-minute recording storyboard, privacy checks, and a release checklist. Record only what the actual run proves.

After the live AI demo prints `PASS` and you review the report, the controlled fixture can be added to the site gallery **as a labelled demo**, not a real scanned website:

```cmd
.venv\Scripts\python.exe scripts\publish_recorded_scan.py output\ai-demo --slug akshara-fixture-demo --title "AksharaCheck controlled demo" --reviewed-public-content --fixture-demo
```

For a real public website, use the regular publisher without `--fixture-demo` (see the recorded-scan instructions below). The reviewed controlled demo and Hindi Wikipedia recording have now been committed and deployed.

## Website experience

The frontend follows the **Attested school-copybook** identity: paper ground, ruled blue lines, correction red, verified green, fountain-pen blue-black and the circular AksharaCheck mark. Fonts are bundled from Fontsource's Anek Latin, Devanagari and Kannada variable families so visitors do not depend on a Google Fonts request. The masthead, browser tab title and SVG favicon use this identity.

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

## Live BharatCode smoke test and local AI demo

Use an API key from [your BharatCode account](https://bharatcode.ai/account). Never paste a key into a chat, issue, commit, browser frontend or screenshot. The smoke test below prompts for a key without showing the characters if `BHARATCODE_API_KEY` is not set:

```cmd
.venv\Scripts\python.exe scripts\check_bharatcode.py
```

A passing result confirms an authenticated API request and structured English, Hindi and Kannada response fields. It does **not** prove the browser repair loop yet.

After that, run a single real model-assisted finding before attempting all nine, to keep failures easy to diagnose:

```cmd
.venv\Scripts\python.exe scripts\run_ai_demo.py --max-findings 1
```

Once that succeeds, run the full AI demonstration. The test page has nine findings to fix or check; saved progress means each run only asks BharatCode about the ones not yet explained, so you can also climb in steps (5, then 9):

```cmd
.venv\Scripts\python.exe scripts\run_ai_demo.py --max-findings 9
start output\ai-demo\report.html
```

The demo runs the scanner in an isolated working directory and preserves your previous successful HTML/JSON/Markdown report and screenshots if a model request fails. After each **completed** model explanation it writes a credential-free local progress checkpoint to `output/ai-demo/.ai-progress.json`. A failed run also creates a separately labelled report at `output/ai-demo/partial/report.html`, so the latest browser evidence and completed AI explanations can be reviewed without misrepresenting the demo as a full PASS. The partial report is removed when a full run succeeds. Use `--no-partial-report` to disable this extra report.

The local demonstration uses BharatCode's **streaming Responses** endpoint. Its documented keepalive events help sustain a request while shared-capacity generation is queued. A stream is considered successful only after a `response.completed` event and valid structured output; incomplete streams are not accepted as model results. If the request still fails, the terminal distinguishes connection failure, missing response/keepalives, and provider status codes.

**If streaming ends with `response.failed`:** BharatCode's documentation says this can happen when shared model capacity is busy after the stream starts. This is **not** a failed Chromium repair, and it does **not** establish that your key was rejected. The current diagnostic cannot distinguish every provider-side cause. The client retries an explicit `response.failed` at most twice (three attempts total), with exponential backoff. If all attempts fail, the diagnostic includes the last provider request ID when supplied and safe to show. Keep the previously generated checkpoint and retry during a less congested period. Rather than repeatedly starting nine fresh requests, progress in stages: `--max-findings 3`, then `5`, then `9`. Each successful finding is saved, and earlier verified repairs are rechecked in Chromium.

**If the second (or later) finding times out:** run the **same command again**, `.venv\Scripts\python.exe scripts\run_ai_demo.py --max-findings 5`. Completed findings are resumed from previous BharatCode model calls, and verified repairs must pass a **fresh Chromium check**. Only pending findings request new model generations. The completed report labels how many explanations came from previous successful sessions, and does not count reused answers as new model calls.

To deliberately ignore earlier progress and make new model requests for every finding, use `--fresh` (for example, `scripts\run_ai_demo.py --max-findings 5 --fresh`). The checkpoint contains only public fixture explanations and repair data, **never API keys**. If the fixture or scanner/AI implementation changes, its saved results are invalidated automatically.

A successful run is required before the main report is replaced. A failed model request retains the previous completed report and saves a separately labelled partial report. The terminal provides a safe diagnostic such as HTTP 401, provider-ended stream, incomplete output, or network/queue timeout without printing keys, authorization headers, or raw model responses. A failed or incomplete stream is never counted as successful AI work.

**If a successful model call is followed by HTTP 401:** run `scripts/check_bharatcode.py` again and enter the *same account's* key through the hidden prompt. If the catalog or generation now rejects the key, review its validity and privileges in the BharatCode account. If the smoke test still returns HTTP 200 but the demo returns HTTP 401, share only sanitized status codes with the provider; do not paste the key or raw authorization headers anywhere. Read the repair status on each finding. Never present a suggested fix as verified unless the independent browser recheck passes.

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

## GitHub Pages preview (static frontend only)

GitHub Pages hosts the React homepage and browser-only Hindi/Kannada text checker. It **cannot** run FastAPI or Playwright and is **not** the complete scanner. The Pages build visibly labels the missing server feature rather than pretending scans are available. Keep a secure HTTPS backend as a separate release milestone.

The public repository is `ashh-droid/AksharaCheck`. Local development uses the normal `/` base; the Pages build uses `/AksharaCheck/` so fonts, scripts and favicon load correctly. From the checkout of the PR branch on Windows:

```cmd
git pull
cd web
npm run deploy:pages
```

The command builds the frontend and publishes **only** `web/dist` to an independent `gh-pages` branch. It does not merge the source PR and does not require a custom GitHub Actions workflow. It does require working Git credentials and an npm connection.

On GitHub, select **Settings > Pages > Build and deployment > Source: Deploy from a branch > Branch: gh-pages / (root) > Save**. GitHub's own Pages deployment job may still run. Once publishing is complete, open `https://ashh-droid.github.io/AksharaCheck/` and confirm the logo, text checker, navigation, and responsive layouts.

For local production preview before publishing, run `npm run build:pages` followed by `npm run preview`, and visit the `/AksharaCheck/` path displayed by Vite. Opening the server root `/` instead may show an empty or redirected view because the build expects that repository subpath.

The real URL-scanning backend must be deployed independently with Chromium isolation, rate limiting and outbound private-network blocking. Keep `BHARATCODE_API_KEY` server-side. Set `VITE_API_URL` to an authorized HTTPS backend before building a full-stack separated deployment.


## Record a real scan for GitHub Pages

GitHub Pages cannot run Chromium. The static homepage therefore offers a working browser-only Hindi/Kannada text check and links to real recorded Chromium reports **only once files have been reviewed and published**. No fake reports are included.

1. Scan an authorized public page locally: `.venv\Scripts\python.exe -m aksharacheck scan https://hi.wikipedia.org/ --pages 1 --output output\hi-wikipedia-v2`
2. Open `output\hi-wikipedia-v2\report.html`, verify each finding and ensure the report contains no sensitive information, private URLs or unexpected user text.
3. Export that approved report and its screenshots:

```cmd
.venv\Scripts\python.exe scripts\publish_recorded_scan.py output\hi-wikipedia-v2 --slug hindi-wikipedia --title "Hindi Wikipedia" --reviewed-public-content
```

4. Inspect the generated files under `web\public\samples\` and the updated `catalog.json`. Only commit and publish files that you have personally reviewed for privacy and accuracy.
5. Build and deploy the Pages frontend with `cd web && npm install && npm run deploy:pages`. The saved report becomes accessible under `/AksharaCheck/samples/hindi-wikipedia/report.html` and appears in the homepage's recorded-scan section.

A recorded scan is evidence of the browser results at its stated date, not a live scan or an AI-produced fix. **Do not add BharatCode AI explanations until real authorized model calls succeed.**

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

Also run `cd web && npm install && npm run build` and test a complete Chromium scan. GitHub Actions CI is active on this public repository; only merge a branch after its updated automated checks pass.

## Repo and hackathon

1. Register at https://bharatcode.ai/hackathon with your BharatCode account.
2. Publish this folder in a **public** GitHub repository, preserving `BharatCode.txt` at the root.
3. Confirm required file content and any submission-specific deadline with the organizers.
4. Submit the **main repository URL**, not a branch/file link.

## Read and verify the redesigned reports

The HTML report is now an evidence review designed to be readable by customers and judges: a slim Attested masthead, clear browser-check summary, grouped findings with affected words, and expandable measurements. It does not claim suspected clipping or intentional font fallback are proven defects.

An older `report.json` can be **restyled**, but the old findings will not change. It will show an "Earlier scan data" notice. Re-scan to apply the latest clipping thresholds.

```cmd
git pull
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m aksharacheck render output\hi-wikipedia\report.json
start output\ai-demo\report.html
```

Check the report at phone, tablet, and desktop widths. The following automated QA runs a local Chromium review and captures its layout at 320, 360, 390, 768 and 1440 pixels:

```cmd
.venv\Scripts\python.exe scripts\check_report_ui.py output\ai-demo\report.html
```

The screenshots are saved under `output\hi-wikipedia\report-visual-qa`.

After reviewing the appearance, make a **fresh scan** to update the findings:

```cmd
.venv\Scripts\python.exe -m aksharacheck scan https://hi.wikipedia.org/ --pages 1 --output output\hi-wikipedia-fresh
start output\hi-wikipedia-fresh\report.html
```

Compare the warning count with the original six and inspect the remaining flags. Never describe a suspected warning as confirmed without checking the page evidence.


## Release preflight without BharatCode API access

BharatCode API generation currently returns HTTP 402 on accounts without a qualifying entitlement. This does not block the Chromium detector, reports or local repair verification tests.

From the repository root on Windows:

```cmd
git pull
.venv\Scripts\python.exe -m pytest -q
cd web
npm run build
cd ..
.venv\Scripts\python.exe -m aksharacheck --version
```

For one small, authorized real-site scan, use the CLI against a publicly accessible page you are permitted to audit:

```cmd
.venv\Scripts\python.exe -m aksharacheck scan https://hi.wikipedia.org/ --pages 1 --output output/hi-wikipedia
```

Open `output/hi-wikipedia/report.html`. Record any errors, warnings and false positives. Scan just one page at first, and respect the site's robots rules and rate limits.

For a machine-readable report with diagnostic progress on stderr, add `--json`. The CLI defaults to localhost-only serving; `serve --host 0.0.0.0` is intended only for infrastructure that isolates Chromium, blocks private-network egress, and limits public requests.

Do not publish a 100-site claim until the methodology and finding accuracy are reviewed. Do not claim live BharatCode integration success until `scripts/check_bharatcode.py` returns HTTP 200 for generation.

## Next milestone

Run the updated golden tests, test the React build and a live BharatCode API call, validate on a small real-site sample, then deploy and record a 60-second demonstration. Do not claim 90% detection precision or completed 100-site scans until those are actually measured.

**Development disclosure:** ChatGPT assisted with architecture, implementation, testing plans and interface design. The team independently reviewed the original MVP and identified detector and verifier defects that are being corrected in PR #1. A real browser and BharatCode API run is required before calling this release fully validated.
