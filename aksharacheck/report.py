"""Generate independently usable JSON, Markdown, and HTML evidence reports."""
import html
import json
from pathlib import Path


def write_reports(data, dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    (dest/'report.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    s=data['summary'];lines=["# AksharaCheck scan", "", f"Target: `{data['target']}`", f"Findings: {s['error']} errors · {s['warning']} warnings · {s['info']} info",""]
    for f in data['findings']:
        lines.extend([f"## {f['severity'].upper()} — {f['detector']} (`{f['id']}`)","",f"URL: {f['url']} · widths: {', '.join(str(w) + 'px' for w in f.get('viewports', [f['viewport']]))}",f"Selector: `{f['selector']}`",f"Evidence: `{json.dumps(f['evidence'],ensure_ascii=False)}`","",str(f.get('ai_explanation') or ''),""])
        if f.get('fix'):lines.extend([f"Repair check: **{f['fix']['status']}**", ""])
    (dest/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    def esc(x):return html.escape(str(x),quote=True)
    cards=[]
    for f in data['findings']:
        fix=f.get('fix') or {}
        details=esc(json.dumps(f['evidence'],indent=2,ensure_ascii=False))
        image=f.get('element_screenshot') or f.get('screenshot','')
        img=f'<a href="{esc(image)}" target="_blank" rel="noopener"><img src="{esc(image)}" alt="Browser evidence screenshot" loading="lazy"></a>' if image else ''
        verified='Verified in browser' if fix.get('status')=='verified' else ('Not automatically repairable' if fix.get('status')=='not-applicable' else 'Not verified')
        css=esc(json.dumps(fix.get('css'),indent=2)) if fix.get('css') else ''
        cards.append(f'<article class="finding"><div class="finding-head"><span class="severity {esc(f["severity"])}">{esc(f["severity"])}</span><strong>{esc(f["detector"])}</strong><span>{esc(", ".join(str(w)+"px" for w in f.get("viewports",[f["viewport"]])))}</span></div><p class="muted">{esc(f["url"])} · {esc(f["selector"])}</p><p>{esc(f["sample"])}</p><details><summary>Browser evidence</summary><pre>{details}</pre></details>{img}<p>{esc(f.get("ai_explanation") or "Deterministic evidence recorded. Run --ai to request a BharatCode explanation and patch.")}</p><p class="verify">{esc(verified)}</p>{f"<pre>{css}</pre>" if css else ""}</article>')
    markup='\n'.join(cards) or '<p class="empty">No findings detected in the evaluated elements. This is not a guarantee of complete language rendering correctness.</p>'
    webpage='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AksharaCheck — Evidence report</title><style>
    @import url('https://fonts.googleapis.com/css2?family=Anek:wght@400;500;600;700;800&family=Anek+Devanagari:wght@400;500;600;700;800&family=Anek+Kannada:wght@400;500;600;700;800&display=swap');
    :root{--paper:#F8FAF7;--ink:#1B2440;--attested:#0E6B4E;--correction:#D9475A;--rule:#B8CCE6;font-family:"Anek","Anek Devanagari","Anek Kannada",system-ui,sans-serif;color:var(--ink);background:var(--paper);line-height:1.6}*{box-sizing:border-box}body{margin:0}header{background:#141B30;color:#f9fcf7;padding:52px max(24px,calc((100vw - 1000px)/2))}header h1{font-size:clamp(32px,6vw,58px);line-height:1.1;margin:0 0 18px}header p{opacity:.84;overflow-wrap:anywhere}main{max-width:1000px;margin:auto;padding:35px 20px}h2{font-size:25px;margin-top:36px}.counts{font-size:22px;font-weight:700}.finding{background:white;padding:26px;border:1px solid var(--rule);border-radius:14px;margin:16px 0;box-shadow:0 3px 14px #0822210a;overflow:hidden}.finding-head{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.finding-head span:last-child{margin-left:auto;color:#5b6967}.severity{font-size:12px;text-transform:uppercase;letter-spacing:.07em;border-radius:5px;padding:3px 9px;background:#e7efeb}.severity.error{background:#ffdfdb;color:#B8323F}.severity.warning{background:#fff0d1;color:#8e570c}.severity.info{color:#336064}.muted{color:#697b79;font-size:13px;overflow-wrap:anywhere}.finding img{display:block;max-width:100%;max-height:320px;object-fit:contain;margin:14px 0;border:1px solid #d6e0dc}.finding pre{overflow:auto;font-size:12px;background:#eff4f1;padding:15px;border-radius:6px}.verify{font-weight:700;color:var(--attested)}.empty{padding:32px;background:white;border-radius:14px}footer{margin:50px auto;color:#687873}
    </style></head><body><header><div>अ · ಅ</div><h1>AksharaCheck</h1><p>Evidence-first rendering audit · <strong>'''+esc(data['target'])+'''</strong></p></header><main><div class="counts">'''+f"{s['error']} errors · {s['warning']} warnings · {s['info']} informational"+'''</div><p>Measured by Chromium. AI suggestions are not findings; only independent browser rechecks count as verified repairs.</p><h2>Findings</h2>'''+markup+'''<footer>AksharaCheck v0.1 · Generated browser evidence is not proof of exhaustive correctness.</footer></main></body></html>'''
    (dest/'report.html').write_text(webpage,encoding='utf-8')
