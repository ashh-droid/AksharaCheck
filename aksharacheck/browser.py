"""Playwright browser scanner with conservative request routing."""
import asyncio
import os
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag
from playwright.async_api import async_playwright
from .security import validate_url, UnsafeURL
from .detectors import run_dom_detectors, failed_font_findings, font_mismatch_findings

DOM_JS = r'''(args) => {
 const out=[]; const root=document.body; if(!root)return out;
 const walker=document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
 const seen=new Set();let el;let index=0;
 while((el=walker.nextNode()) && index < 650){
   if(['SCRIPT','STYLE','NOSCRIPT','SVG','OPTION'].includes(el.tagName))continue;
   const direct=[...el.childNodes].filter(n=>n.nodeType===3).map(n=>n.textContent).join(' ').trim();
   if(!direct || direct.length<2)continue;
   const cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden')continue;
   let selector=el.getAttribute('data-akshara-id');
   if(!selector){selector='ak-'+(++index);el.setAttribute('data-akshara-id',selector)}
   const rect=el.getBoundingClientRect();
   let p=el,lang='';while(p){if(p.getAttribute?.('lang')){lang=p.getAttribute('lang');break}p=p.parentElement}
   const fs=parseFloat(cs.fontSize)||0; const lh=cs.lineHeight==='normal'?0:(parseFloat(cs.lineHeight)||0);
   out.push({selector:`[data-akshara-id="${selector}"]`, text:direct.slice(0,600), font:cs.fontFamily,
    fontSize:fs,lineHeight:lh,lang,clientWidth:el.clientWidth,scrollWidth:el.scrollWidth,
    clientHeight:el.clientHeight,scrollHeight:el.scrollHeight,overflowX:cs.overflowX,
    overflowY:cs.overflowY,lineCount:fs?Math.max(1,Math.round(rect.height/(lh||fs*1.2))):1,
    intentionalClamp:cs.webkitLineClamp!=='none'||cs.textOverflow==='ellipsis',
    bounds:{x:Math.round(rect.x),y:Math.round(rect.y),w:Math.round(rect.width),h:Math.round(rect.height)}});
 }
 return out;
}'''

class Scanner:
    def __init__(self, output_dir="output", *, allow_local=False, max_pages=1, timeout=60):
        self.output_dir=Path(output_dir)
        self.output_dir.mkdir(parents=True,exist_ok=True)
        self.allow_local=allow_local
        self.max_pages=min(10,max(1,int(max_pages)))
        self.timeout=min(60,max(5,int(timeout)))

    async def scan(self, url, lang="both", progress=None):
        validate_url(url,allow_local=self.allow_local)
        if lang not in {"both","hi","kn"}:raise ValueError("Language must be both, hi or kn")
        async def notify(message):
            if progress:
                value=progress(message)
                if asyncio.iscoroutine(value):await value
        async def task():
            async with async_playwright() as p:
                browser=await p.chromium.launch(headless=True,args=["--no-sandbox"], **({"executable_path":os.environ["AKSHARA_CHROMIUM_PATH"]} if os.environ.get("AKSHARA_CHROMIUM_PATH") else {}))
                try:
                    context=await browser.new_context(ignore_https_errors=False,accept_downloads=False)
                    async def route_handler(route):
                        request=route.request
                        u=request.url
                        if u.startswith(("data:","blob:","about:")):
                            await route.continue_();return
                        try:
                            validate_url(u,allow_local=self.allow_local)
                        except (UnsafeURL, ValueError):
                            await route.abort();return
                        if request.method not in {"GET","HEAD"}:
                            await route.abort();return
                        if request.resource_type in {"websocket","eventsource","media"}:
                            await route.abort();return
                        await route.continue_()
                    await context.route("**/*",route_handler)
                    page=await context.new_page()
                    visited=set();todo=[url];results=[]
                    root_host=urlsplit(url).hostname
                    while todo and len(visited)<self.max_pages:
                        next_url=todo.pop(0)
                        canonical=urldefrag(next_url).url
                        if canonical in visited:continue
                        visited.add(canonical)
                        await notify(f"Opening {canonical}")
                        for viewport in [390,1440]:
                            await page.set_viewport_size({"width":viewport,"height":850 if viewport==390 else 900})
                            failures=[]
                            def response_handler(response):
                                if (response.status >= 400 and re.search(r"\.(?:woff2?|ttf|otf)(?:\?|$)",response.url,re.I)):
                                    failures.append({"font_url":response.url.split("?")[0],"status":response.status})
                            def failed_handler(request):
                                if request.resource_type=="font":failures.append({"font_url":request.url.split("?")[0],"error":"request failed"})
                            page.on("response",response_handler);page.on("requestfailed",failed_handler)
                            try:
                                response=await page.goto(canonical,wait_until="domcontentloaded",timeout=15000)
                                if response and response.status>=400:
                                    await notify(f"HTTP {response.status} at {canonical}")
                                # Browsers can redirect. Validate final URL as well.
                                validate_url(page.url,allow_local=self.allow_local)
                                await page.evaluate("document.fonts.ready")
                                nodes=await page.evaluate(DOM_JS,{})
                                cdp=await context.new_cdp_session(page)
                                try:
                                    await cdp.send('DOM.enable');await cdp.send('CSS.enable')
                                    doc=(await cdp.send('DOM.getDocument'))['root']['nodeId']
                                    # Limit CDP calls to visible likely Indic samples.
                                    from .detectors import indic_share
                                    for node in nodes[:100]:
                                        if indic_share(node['text'])<.2:continue
                                        try:
                                            n=(await cdp.send('DOM.querySelector',{'nodeId':doc,'selector':node['selector']}))['nodeId']
                                            node['platform_fonts']=(await cdp.send('CSS.getPlatformFontsForNode',{'nodeId':n})).get('fonts',[])
                                        except Exception: pass
                                finally:
                                    await cdp.detach()
                                findings=run_dom_detectors(page.url,viewport,nodes,lang)
                                findings+=failed_font_findings(page.url,viewport,failures)
                                findings+=font_mismatch_findings(page.url,viewport,nodes)
                                shot=self.output_dir / f"page-{len(visited):02d}-{viewport}.png"
                                await page.screenshot(path=str(shot),full_page=False,animations="disabled")
                                for f in findings:
                                    f['screenshot']=shot.name
                                    f['bounds']=next((n['bounds'] for n in nodes if n['selector']==f['selector']),None)
                                results.append({"url":page.url,"viewport":viewport,"screenshot":shot.name,"findings":findings,"nodes_checked":len(nodes)})
                                await notify(f"Checked {viewport}px · {len(findings)} findings")
                                if viewport==1440 and len(visited)<self.max_pages:
                                    links=await page.eval_on_selector_all('a[href]', '(a) => a.map(x=>x.href).slice(0,40)')
                                    for link in links:
                                        if urlsplit(link).hostname==root_host and link not in todo and urldefrag(link).url not in visited:
                                            todo.append(link)
                            except Exception as exc:
                                results.append({"url":canonical,"viewport":viewport,"error":str(exc),"findings":[]})
                                await notify(f"Scan error: {str(exc)[:100]}")
                            finally:
                                page.remove_listener('response',response_handler)
                                page.remove_listener('requestfailed',failed_handler)
                    await context.close()
                    return results
                finally:await browser.close()
        pages=await asyncio.wait_for(task(),timeout=self.timeout)
        if pages and all("error" in item for item in pages):
            raise RuntimeError("Browser navigation failed at both viewports: " + str(pages[0].get("error", "unknown failure"))[:200])
        all_findings=[f for p in pages for f in p['findings']]
        output={"version":"0.1.0","target":url,"language":lang,"pages":pages,
                "findings":all_findings,"summary":{s:sum(f['severity']==s for f in all_findings) for s in ('error','warning','info')}}
        (self.output_dir/'report.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
        return output
