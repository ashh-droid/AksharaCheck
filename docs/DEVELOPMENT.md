# Developing AksharaCheck

Commands are for Windows Command Prompt from the repository root. On macOS and Linux, use `.venv/bin/python` in place of `.venv\Scripts\python.exe`.

## BharatCode

- Model `qwen-3.8-27b`, endpoint `https://bharatcode.ai/api/model/v1/responses`, streaming Responses with structured JSON output.
- Get a key from your BharatCode account and keep it in the `BHARATCODE_API_KEY` environment variable on the machine that runs the scanner. Never put it in the website, a commit, an issue or a screenshot.
- Check the key and the model with `.venv\Scripts\python.exe scripts\check_bharatcode.py`. It asks for the key at a hidden prompt if the variable is not set. A pass confirms an authenticated call with English, Hindi and Kannada fields; it does not exercise the browser loop.

### The demo script

`scripts\run_ai_demo.py --max-findings N` serves `fixtures/toota-akshar` on a local port, scans it and runs the BharatCode and Chromium loop for up to N of its nine findings to fix or check. Start with `--max-findings 1`, then `9`.

- After each completed finding it saves a key-free checkpoint in `output\ai-demo\.ai-progress.json`. Running the same command again reuses those explanations, retests their saved repairs in a fresh Chromium, and only asks BharatCode about the rest. The report says how many explanations were reused.
- The checkpoint is invalidated automatically when `ai.py`, `browser.py`, `detectors.py` or the fixture changes. `--fresh` ignores it on purpose.
- The main report in `output\ai-demo` is replaced only after a full pass. A failed run leaves it alone and writes a labelled partial report to `output\ai-demo\partial`. `--no-partial-report` turns that off.

### When BharatCode fails

- **`response.failed` during a stream:** BharatCode's documentation lists this as a possible outcome when shared capacity is busy. It is not a rejected repair and does not mean the key is wrong. The client retries twice with backoff and prints the provider request ID when one is given. Wait and run the same command again, or climb in steps (3, then 5, then 9).
- **A timeout on a later finding:** run the same command again; completed findings are kept.
- **HTTP 401 after earlier successes:** run `check_bharatcode.py` again with the same account's key. If it passes there but not in the demo, share only the status codes with the provider.
- **HTTP 402:** the account is not enabled for model generation.

## Reports

- `aksharacheck render output\some-scan\report.json` rebuilds the HTML and Markdown from a saved scan without a new scan or model calls. Run it after updating the report design.
- `scripts\check_report_ui.py output\some-scan\report.html` opens a report in Chromium at 320, 360, 390, 768 and 1440 px. It checks the header, one card per finding, overview links, images, sideways scrolling, the language switch and both download buttons, and saves screenshots to `report-visual-qa` next to the report.
- A report built from an older scanner shows an "Earlier scan data" notice. Scan again to apply the current rules.

## Publishing a recorded scan to the website

GitHub Pages cannot run Chromium, so the website shows reports recorded on your machine.

1. Scan a public page you are allowed to check: `.venv\Scripts\python.exe -m aksharacheck scan https://hi.wikipedia.org/ --pages 1 --output output\hi-wikipedia`
2. Open the report and check every finding, and that it contains no private text or addresses.
3. Copy it into the website: `.venv\Scripts\python.exe scripts\publish_recorded_scan.py output\hi-wikipedia --slug hindi-wikipedia --title "Hindi Wikipedia" --reviewed-public-content`. Add `--fixture-demo` for the test page, which the website then labels as a demonstration.
4. Review the files in `web\public\samples`, commit them, and publish the website.

## The website

- `web/src/main.tsx` and `web/src/style.css` are the whole site. The site is light only, also in browser dark mode.
- Local development: run `aksharacheck serve --port 8000` in one terminal and `npm run dev` in `web` in another, then open http://127.0.0.1:5173. Vite forwards `/api` to the server.
- `npm run build` builds for the local server, which serves `web/dist` at http://127.0.0.1:8000.
- `npm run deploy:pages` builds with the `/AksharaCheck/` base and publishes `web/dist` to the `gh-pages` branch. Always publish this way, never by editing files on `gh-pages`, so the live site always matches the source.
- `scripts\check_web_ui.py --url http://127.0.0.1:5173` checks the site at nine widths from 320 to 1920 px.

## The scanning server

`aksharacheck serve` binds to 127.0.0.1 by default. It refuses local and private addresses, limits each visitor to five scans an hour and runs at most two at once, but a public deployment still needs Chromium isolated from the internal network, an external rate limiter and a budget limit on model calls. Set `VITE_API_URL` to that server's HTTPS address before building the website to connect the two.
