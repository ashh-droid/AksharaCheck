# Codex task allocation — use only if it saves time

Main objective: ship AksharaCheck as an evidence-first BharatCode hackathon entry. Do NOT rewrite the architecture or switch APIs. Do NOT mark unverified fixes as verified.

## Task 1 (highest priority): Browser integration and detector precision

Read `aksharacheck/browser.py`, `detectors.py`, and `fixtures/toota-akshar`.

Run `scripts/setup_windows.bat` (or the commands in README). Run Chromium against both fixture pages, capture actual screenshots at 390/1440px. Fix every runtime failure, stabilize browser event listeners, ensure actual-font CDP runs. Add integration tests for both the broken and clean fixtures, plus golden findings with no surprise false positives. Make sure the UI does NOT show "clean" when navigation failed. No changes to the BharatCode API routing. Do not remove SSRF guards.

Definition of done: end-to-end Chromium fixture scan works; broken fixture findings are measurable; clean fixture has no error or warning; all tests pass. Include measured numbers, no invented precision percentages.

## Task 2: Repair-loop end-to-end

Read `aksharacheck/ai.py` and https://bharatcode.ai/build. With a developer-provided server-side key, test the exact `/responses` request with model `qwen-3.8-27b` and `store:false`. Confirm structured output schema compatibility. Keep CSS whitelist and finding ID validation. Build at least 3 cases where a CSS patch is browser-verified and 2 unsafe/ineffective CSS patches are explicitly not verified. Never log API key or add it to Git.

Definition of done: actual API call returns structured content; 3/3 supported CSS test fixes verified in fresh Chromium; unfixable cases remain unverified.

## Task 3: Deployment, reliability and demo

Host the FastAPI/Chromium backend in a container with memory/CPU and request caps and the bundled web interface. Add cleanup for old screenshots, a persistent scan/job queue and rate-limiting at the edge. Create an honest 60-second screencast using the seeded fixture and a fully traced browser repair. Verify all links, endpoints and responsive widths. Keep `.github/workflows` disabled unless the owner explicitly requests billing-impacting Actions.

Definition of done: public HTTPS preview works with key only on backend; local and deployment scan tested; README documents limitations and reproducibility.

## Handoff instructions to Codex

Implement one task per branch and one pull request per task. Do not make broad visual redesigns. Do not add libraries for tasks achievable with current stack. Run Python tests and frontend checks. Explain commands run and bugs fixed. Do not make network requests to arbitrary private IPs or bypass sites that reject crawlers.
