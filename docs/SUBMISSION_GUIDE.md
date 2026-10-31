# BharatCode Build League submission and video guide

Official entry: https://bharatcode.ai/hackathon

Deadline stated on the official page: **10 November 2026, 11:59 PM IST**. Required on the public page: a public GitHub repository, `BharatCode.txt` in the root, a working BharatCode-powered project, and the main repository URL entered in the submission form. The page does not currently list a mandatory video or presentation upload. Confirm the signed-in form before submitting.

## Proposed title

AksharaCheck — Find the letters your website breaks

## Proposed 1,000-character summary

AksharaCheck finds Hindi and Kannada text that websites render wrongly: broken letters, clipped vowel marks, overflowing lines and text tagged with the wrong language. It opens a page in Chromium at phone and desktop widths and records evidence: screenshots, Unicode code points and measurements. BharatCode's qwen-3.8-27b then explains each finding in English, Hindi and Kannada and proposes a repair limited to safe CSS or a lang attribute. Chromium tests every proposal in a fresh page and marks it verified only if the problem is gone and the text stays visible, full size and on screen; a rejected proposal goes back to the model with the reason. In the demo, BharatCode explained 9 of 9 findings and Chromium verified 4 repairs. On the Karnataka government news site, it found 72 pieces of Kannada text announced as English because of one page-level tag. Built with Python, Playwright, FastAPI, React and Vite.

The nine-finding run passed on 31 October 2026 (9 of 9 explained, 4 repairs verified in Chromium), so the summary may say so. Re-check this line if the demo is run again on a later revision.

## 2–3-minute demonstration plan (using real saved evidence)

| Video time | What to show | Proof |
|---|---|---|
| 00:00–00:20 | Broken Hindi/Kannada text on the clearly labelled local test page | Genuine fixture, not a real government website |
| 00:20–00:55 | Open the published BharatCode demonstration report: 3 Fix, 6 Check, 2 Note, with 9/9 actionable findings explained | Real saved report, no new API calls |
| 00:55–01:25 | Switch one explanation between English, Hindi and Kannada | Actual BharatCode-generated text from the stored run |
| 01:25–01:55 | Show the rejected overflow repair, the accepted one and both screenshots | Existing Chromium attempt trail; don't manufacture a repair |
| 01:55–02:20 | Open reviewed Karnataka Varthe Kannada scan: 72 observations inheriting `lang=en` from one HTML element | Dated browser capture, not a screen-reader experiment |
| 02:20–02:40 | Open the clean DD News Hindi scan with 162/213 sampled elements and page screenshots | Browser-only scan, not site-wide certification |
| 02:40–03:00 | Show the GitHub repository, `BharatCode.txt`, and the no-key browser scan command | Reproducible setup |

**Important:** Avoid showing a secret API key or claiming a recorded report is a live model stream. The published 9/9 BharatCode result remains valid as a dated snapshot; rerunning after detector changes can require **nine fresh model calls**. The video is recommended for explaining the product, but the public rules page does not explicitly require one; verify the signed-in submission form.

## Windows release checks without new BharatCode API calls

From `C:\Projects\AksharaCheck` after pulling the latest `main`:

```cmd
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe scripts\check_report_ui.py web\public\samples\akshara-fixture-demo\report.html
.venv\Scripts\python.exe scripts\check_report_ui.py web\public\samples\karnataka-varthe-kannada\report.html
.venv\Scripts\python.exe scripts\check_report_ui.py web\public\samples\dd-news-hindi\report.html
```

Open the reviewed [controlled BharatCode report](https://ashh-droid.github.io/AksharaCheck/samples/akshara-fixture-demo/report.html), [Kannada report](https://ashh-droid.github.io/AksharaCheck/samples/karnataka-varthe-kannada/report.html), and [Hindi report](https://ashh-droid.github.io/AksharaCheck/samples/dd-news-hindi/report.html). Confirm each screenshot and JSON/Markdown download on desktop and phone. The archived Hindi Wikipedia report does not appear in the final homepage gallery.

Only if the website source or gallery was changed and tests passed, deploy it using:

```cmd
cd web
npm install
npm run deploy:pages
```

This publishes static files to GitHub Pages; the live Chromium scanner still runs locally or on a separately secured backend. **Do not re-run `run_ai_demo.py` as a release preflight.**

## Final Windows fresh-clone QA

Use an empty folder, new virtual environment, installed Chromium, a scan of a permitted public URL, and a local browser to open the generated HTML. Confirm Devanagari and Kannada text render correctly even when offline after generating the report. Test on phone and desktop widths. Inspect links, copyright/attribution, `BharatCode.txt`, no API secrets in the repository, and that the submission URL points to the repo root.

**Do not confuse GitHub Pages with the full app.** The Pages preview offers a browser-side text checker and recorded evidence. Live URL scans need a properly isolated backend; the README says this in "Run the web app locally".

## Deadline checklist

- [ ] BharatCode account registration and submission form verified while logged in
- [x] Main branch merged with passing CI, no demo blockers
- [x] Nine-finding BharatCode run PASS (9 of 9 explained, 4 verified repairs)
- [x] Reviewed controlled fixture demo published and labelled
- [x] Reviewed public-page scans published: Karnataka Varthe (Kannada) and DD News (Hindi)
- [x] README screenshots captured from an actual report and linked
- [ ] 2–3-minute video recorded from actual steps and linked, if completed
- [ ] Fresh Windows clone and Chromium report checked
- [ ] Public GitHub repo with `BharatCode.txt` confirmed
- [ ] Main repository URL submitted on https://bharatcode.ai/hackathon before the official deadline
