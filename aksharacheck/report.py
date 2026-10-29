"""Generate independently usable JSON, Markdown, and HTML evidence reports."""
import html
import json
from pathlib import Path


def write_reports(data, dest):
    dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
    (dest/'report.json').write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    s=data['summary'];lines=["# AksharaCheck scan", "", f"Target: `{data['target']}`", f"Findings: {s['error']} errors · {s['warning']} warnings · {s['info']} info",""]
    if data.get("demo_mode"):
        lines[1:1]=["**OFFLINE DEVELOPMENT DEMO. No BharatCode API was called. Sample repairs are human-authored rules.**", ""]
    for f in data['findings']:
        lines.extend([f"## {f['severity'].upper()} : {f['detector']} (`{f['id']}`)","",f"URL: {f['url']} · widths: {', '.join(str(w) + 'px' for w in f.get('viewports', [f['viewport']]))}",f"Selector: `{f['selector']}`",f"Evidence: `{json.dumps(f['evidence'],ensure_ascii=False)}`","",str(f.get('ai_explanation') or ''),""])
        if f.get('fix'):lines.extend([f"Repair check: **{f['fix']['status']}**", ""])
    (dest/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    def esc(x):return html.escape(str(x),quote=True)
    cards=[]
    for f in data['findings']:
        fix=f.get('fix') or {}
        details=esc(json.dumps(f['evidence'],indent=2,ensure_ascii=False))
        image=f.get('element_screenshot') or f.get('screenshot','')
        img=f'<a href="{esc(image)}" target="_blank" rel="noopener"><img src="{esc(image)}" alt="Browser evidence screenshot" loading="lazy"></a>' if image else ''
        state=fix.get('status')
        verified='Verified in Chromium' if state=='verified' else ('Manual repair needed' if state=='not-applicable' else ('Repair not verified' if fix else 'No repair requested'))
        state_class='ok' if state=='verified' else ('pending' if state in {'unverified','unavailable'} else 'neutral')
        css=esc(json.dumps(fix.get('css'),indent=2)) if fix.get('css') else ''
        scopes=" + ".join("Phone" if w<=430 else "Desktop" for w in f.get("viewports",[f["viewport"]]))
        explanation=esc(f.get('ai_explanation') or "This finding comes from a browser measurement. No AI explanation has been requested.")
        patch=f"<pre class='patch'>{css}</pre>" if css else ""
        media=f'<div class="media">{img}</div>' if img else ""
        card=(f'<article class="finding"><div class="finding-head">'
              f'<span class="severity {esc(f["severity"])}">{esc(f["severity"])}</span>'
              f'<strong>{esc(f["detector"].replace("-", " ").capitalize())}</strong>'
              f'<span class="scope">{esc(scopes)}</span></div>'
              f'<p class="sample">{esc(f["sample"])}</p>'
              f'<div class="finding-body">{media}'
              f'<div class="finding-copy"><p>{explanation}</p>'
              f'<p class="verify {state_class}">{esc(verified)}</p>{patch}</div></div>'
              f'<details><summary>Show measured evidence</summary><pre>{details}</pre>'
              f'<p class="muted">{esc(f["url"])} · {esc(f["selector"])}</p></details></article>')
        cards.append(card)
    markup='\n'.join(cards) or '<p class="empty">No findings detected in the evaluated elements. This is not a guarantee of complete language rendering correctness.</p>'
    if data.get("demo_mode"):
        markup=('<div class="demo-banner" role="note"><strong>Offline development demo</strong>. '
                'No BharatCode model was called. Proposed repairs are local, predefined examples, '
                'and their verification status reflects only Chromium checks.</div>')+markup
    webpage='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AksharaCheck | Browser evidence report</title><style>
    @import url('https://fonts.googleapis.com/css2?family=Anek:wght@400;500;600;700;800&family=Anek+Devanagari:wght@400;500;600;700;800&family=Anek+Kannada:wght@400;500;600;700;800&display=swap');
    :root{--paper:#F8FAF7;--ink:#1B2440;--attested:#0E6B4E;--correction:#D9475A;--rule:#B8CCE6;font-family:"Anek","Anek Devanagari","Anek Kannada",system-ui,sans-serif;color:var(--ink);background:var(--paper);line-height:1.6}*{box-sizing:border-box}body{margin:0}header{background:#141B30;color:#f9fcf7;padding:52px max(24px,calc((100vw - 1000px)/2))}header h1{font-size:clamp(32px,6vw,58px);line-height:1.1;margin:0 0 18px}header p{opacity:.84;overflow-wrap:anywhere}main{max-width:1100px;margin:auto;padding:42px 24px}h2{font-size:25px;margin-top:36px}.counts{font-size:22px;font-weight:700}.finding{background:white;padding:28px;border:1px solid #D6E0E7;border-radius:9px;margin:20px 0;box-shadow:0 8px 22px #1B244009;overflow:hidden}.finding-head{display:flex;align-items:center;gap:16px;flex-wrap:wrap}.finding-head .scope{margin-left:auto;color:#40516B;font-size:13px}.severity{font-size:12px;text-transform:uppercase;letter-spacing:.07em;border-radius:5px;padding:3px 9px;background:#e7efeb}.severity.error{background:#ffdfdb;color:#B8323F}.severity.warning{background:#fff0d1;color:#8e570c}.severity.info{color:#336064}.muted{color:#697b79;font-size:13px;overflow-wrap:anywhere}.finding img{display:block;max-width:100%;max-height:300px;object-fit:contain;margin:0;border:1px solid #D6E0E7}.finding pre{overflow:auto;font-size:12px;background:#eff4f1;padding:15px;border-radius:6px}.verify{font-weight:700;font-size:14px;line-height:1.4}.verify.ok{color:var(--attested)}.verify.pending{color:#B8323F}.verify.neutral{color:#46516B}
    .sample{font-size:21px;line-height:1.65;overflow-wrap:anywhere;border-bottom:1px solid #D6E0E7;padding:12px 0;margin:8px 0 18px}
    .finding-body{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr);gap:24px;align-items:start}
    .finding-body:not(:has(.media)){grid-template-columns:1fr}
    .finding-copy p:first-child{font-size:15px;color:#40516B}
    .media{min-width:0;background:#F8FAF7;border:1px solid #D6E0E7;padding:10px}
    .patch{border-left:3px solid var(--attested);background:#E3F1EA!important}
    .finding details{border-top:1px solid #D6E0E7;margin-top:20px;padding-top:12px}
    .finding details summary{cursor:pointer;color:#0E6B4E;font-weight:650}
    .demo-banner{border-left:4px solid #B8323F;background:#FBE7E9;padding:16px 18px;margin:22px 0;color:#1B2440;line-height:1.5}
    @media(max-width:720px){header{padding:32px 20px}main{padding:28px 16px}.finding{padding:18px}.finding-body{grid-template-columns:1fr}.finding-head .scope{flex-basis:100%;margin-left:0}}.empty{padding:32px;background:white;border-radius:14px}footer{margin:50px auto;color:#687873}
    </style></head><body><header><div style="display:flex;align-items:center;gap:12px"><svg aria-hidden="true" width="37" height="37" viewBox="0 0 120 120"><path d="M49.65 21.36 A40 40 0 1 1 49.65 98.64" fill="none" stroke="#3FB58A" stroke-width="13" stroke-linecap="round"/><g fill="#F07A88"><circle cx="34.83" cy="91.08" r="6.5"/><circle cx="24.05" cy="77.54" r="6.5"/><circle cx="20" cy="60" r="6.5"/><circle cx="24.05" cy="42.46" r="6.5"/><circle cx="34.83" cy="28.92" r="6.5"/></g></svg><h1>AksharaCheck</h1></div><p>Evidence-first rendering audit · <strong>'''+esc(data['target'])+'''</strong></p></header><main><div class="counts">'''+f"{s['error']} errors · {s['warning']} warnings · {s['info']} informational"+'''</div><p>Measured by Chromium. AI suggestions are not findings; only independent browser rechecks count as verified repairs.</p><h2>Findings</h2>'''+markup+'''<footer>AksharaCheck v0.1 · Generated browser evidence is not proof of exhaustive correctness.</footer></main></body></html>'''
    (dest/'report.html').write_text(webpage,encoding='utf-8')
