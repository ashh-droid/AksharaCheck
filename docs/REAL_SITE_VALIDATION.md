# Real-site validation before public case studies

These are **browser observations**, not certified findings about another website. Scan only publicly accessible pages allowed for automated inspection, keep one page per site, avoid repeated requests, and manually review screenshots before publishing claims.

## Karnataka Varthe (Kannada government website)

On 31 October 2026, an initial scan showed **1 error, 134 warnings and 50 informational notes**. The sole error reported the word `ಆ್ಯಪ್` ("app") as a stray virama. That was an **AksharaCheck false positive** in a commonly used Kannada loanword, not a proven site defect. A narrow regression fix preserves ordinary stray-virama detection and a documented Badaga vowel form.

The 133 `wrong-lang` warnings mean that many text elements are inheriting or declaring a language inconsistent with the observed Kannada script (the captured examples reported `en`). This may represent a legitimate accessibility issue, but **133 separate elements are not necessarily 133 distinct root-cause defects**. Inspect whether the document or a common ancestor uses `lang="en"`, and validate whether its `lang` attribute is overridden for Kannada text. The one mobile-overflow warning also requires checking whether any text is actually clipped or inaccessible.

The browser sampler checks a limited set of visible text nodes, so results are not a comprehensive audit of every page or every on-screen element.

Do **not** publish the pre-fix "1 broken letter" headline as a confirmed government website defect.

## Prajavani (Kannada news)

The 31 October scan showed **0 errors, 0 warnings, 58 notes**. All notes report a difference between the requested CSS font and the font Chromium actually used, including the site's Prajavani typeface. Such fallback/substitution can be intentional. Do not claim 58 bugs.

## Run a corrected Kannada scan

After pulling the approved detector change into the local checkout:

```cmd
cd /d C:\Projects\AksharaCheck
.venv\Scripts\python.exe -m aksharacheck scan https://varthe.karnataka.gov.in/ --lang kn --pages 1 --output output\karnataka-varthe-v2
start output\karnataka-varthe-v2\report.html
```

Expected from the corrected rule: the specific `ಆ್ಯಪ್` sequence is no longer an invalid-cluster error. Other findings may change if the live page has changed. Verify the resulting counts and examine the `wrong-lang` warning details before drawing conclusions.

**Published result (31 October 2026, scanner `2026-10-31-precision`):** 0 errors, 73 warnings and 13 notes. 72 of the warnings are Kannada text inheriting `lang="en"` from the page's `<html>` element, one root cause that a single tag change fixes; the report says so above the cards. The remaining warning is one possible overflow at phone width that needs a visual check. This is the report linked from the website.

## One Hindi page: DD News

Official Hindi news homepage: https://ddnews.gov.in/ . This currently shows Hindi news content; check the actual loaded result before interpreting any findings.

```cmd
.venv\Scripts\python.exe -m aksharacheck scan https://ddnews.gov.in/ --lang hi --pages 1 --output output\dd-news-hindi
start output\dd-news-hindi\report.html
```

This scans the accessible public page at phone (390px) and desktop (1440px). A valid clean scan is still useful evidence. If any defect is suspected, manually inspect the exact screenshot, selector, language attribute and rendered characters; exclude false alarms and explain limitations before publishing.

## Full saved-report audit, without rescanning or AI calls

The screenshots in a chat show only selected findings. To review every finding, every DOM language-tag warning, every font-mismatch note, scan completeness, and missing screenshot files, run:

```cmd
cd /d C:\Projects\AksharaCheck
.venv\Scripts\python.exe scripts\audit_saved_reports.py output\karnataka-varthe\report.json output\prajavani\report.json
```

This creates **only** `output\karnataka-varthe\audit-review.json` and `output\prajavani\audit-review.json`. The original reports and all image evidence are left untouched. If your outputs use different folder names, substitute their exact paths.

A count summary alone cannot show whether many warnings share one root cause or whether a custom font was really substituted; review the source text, screenshots and codepoints in each report.

## Publication gate

- Confirm the page actually loaded at both widths, without blocked/error responses.
- Explain whether each claimed finding is confirmed, probable or informational.
- Document the URL, UTC scan time, screen widths, and scanner version.
- Compare the source text with the visual screenshot before claiming a broken letter.
- Avoid suggesting a third-party website has 133 separate defects from 133 nested text elements without reviewing inheritance.
- Never fabricate an AI explanation. Public-site scans do not use BharatCode unless an actual API request was made.
- Keep the original nine-finding fixture report as a historical verified snapshot; a detector update does not change what the earlier browser run measured.
