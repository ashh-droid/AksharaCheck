import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ArrowUpRight,ArrowRight,CheckCheck,Code2,ScanSearch,ShieldCheck,FileText,Search, ExternalLink, RotateCcw, AlertTriangle} from 'lucide-react';
import './style.css';

type Fix={status:string,css?:Record<string,string>,attributes?:Record<string,string>,reason?:string};
type Finding={id:string,url:string,viewport:number,viewports?:number[],selector:string,sample:string,detector:string,severity:string,evidence:Record<string,unknown>,screenshot?:string,element_screenshot?:string,ai_explanation?:string,fix?:Fix};
type Report={target:string,summary:{error:number,warning:number,info:number},findings:Finding[],pages:{url:string,viewport:number,screenshot?:string,findings:Finding[],error?:string}[]};
type Job={status:string,events:string[],error?:string,summary?:Report['summary']};
const API=import.meta.env.VITE_API_URL || '';
const examples=['https://www.india.gov.in/','https://en.wikipedia.org/wiki/Hindi'];
const labels:Record<string,string>={'wrong-lang':'Language metadata','broken-cluster':'Unicode letter sequence','mobile-overflow':'Mobile text overflow','possible-clipping':'Possible clipped characters','mixed-language':'Mixed Indic language spans','font-fallback':'Font actually rendered','font-load-failed':'Web font failed','legacy-font':'Legacy encoded text','tight-line-height':'Line spacing'};
function App(){
 const [url,setUrl]=useState('');const [lang,setLang]=useState('both');const [ai,setAi]=useState(false);const [aiAvailable,setAiAvailable]=useState(false);
 const [scanId,setScanId]=useState<string|null>(null);const [job,setJob]=useState<Job|null>(null);
 const [report,setReport]=useState<Report|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 const interval=useRef<number | undefined>(undefined);
 useEffect(()=>{fetch(API+'/api/health').then(r=>r.json()).then(d=>setAiAvailable(Boolean(d.ai_available))).catch(()=>setAiAvailable(false));return ()=>{if(interval.current)window.clearInterval(interval.current)}},[]);
 async function begin(e:React.FormEvent){e.preventDefault();setError('');setReport(null);setJob(null);setBusy(true);
  try{const res=await fetch(API+'/api/scans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url,lang,use_ai:ai})});
  const data=await res.json();if(!res.ok)throw new Error(data.detail||'Could not start scan');setScanId(data.id);
  if(interval.current)window.clearInterval(interval.current);
  const poll=async()=>{try{const s=await fetch(API+'/api/scans/'+data.id);if(!s.ok)throw new Error('Scan not found');const j:Job=await s.json();setJob(j);
   if(j.status==='complete'){window.clearInterval(interval.current);const r=await fetch(API+'/api/scans/'+data.id+'/report');setReport(await r.json());setBusy(false)}
   if(j.status==='error'){window.clearInterval(interval.current);setError(j.error||'Scan failed');setBusy(false)}
  }catch(x){window.clearInterval(interval.current);setError(String(x));setBusy(false)}};await poll();interval.current=window.setInterval(poll,1600);
  }catch(x){setError(x instanceof Error?x.message:String(x));setBusy(false)}}
 function reset(){setScanId(null);setReport(null);setJob(null);setError('');setBusy(false)}
 function asset(name:string){return `${API}/api/scans/${scanId}/artifacts/${name}`}
 return <><header className="topbar"><a className="brand" href="/" onClick={e=>{if(report||job){e.preventDefault();reset()}}}><span className="brand-mark" aria-hidden="true"><span className="broken-dot">◌</span><span className="repair-arc">✓</span></span>Akshara<span>Check</span></a><nav><a href="#how">How it works</a><a href="https://github.com/ashh-droid/AksharaCheck" target="_blank" rel="noreferrer">Open source <ArrowUpRight size={14}/></a></nav></header>
 <main>
  {!report && <section className="hero"><p className="eyebrow">A copybook for the Indic web</p><div className="hero-columns"><div><h1>Every letter<br/>deserves to<br/>render correctly.</h1><p className="lede">Your website may look perfect in English. But what about हिन्दी and ಕನ್ನಡ? Find rendering bugs, see browser evidence, and get fixes that are actually tested.</p><p className="hero-mini">Find the problem. See the proof. Check the repair.</p></div><div className="letter-art" aria-hidden="true"><span className="art-top">Teacher’s correction / Verified repair</span><div className="indic-art"><span className="broken-text">क<span className="art-bad">◌ि</span>ताब</span><ArrowRight className="art-arrow" size={26}/><span className="fixed-text">किताब</span></div><div className="art-bottom"><span className="correction-mark">Needs correction</span><span className="attestation-mark">✓ Verified in browser</span></div></div></div></section>}
  <section className={'scan-panel '+(report?'result-mode':'')}><div className="panel-head"><div><div className="eyebrow minor">{report?'Scan complete':'Start a scan'}</div>{report?<h1 className="report-title">Your rendering audit</h1>:<h2>Put your pages to the test.</h2>}</div>{report&&<button className="secondary" onClick={reset}><RotateCcw size={16}/> New scan</button>}</div>
  {!report && <form onSubmit={begin}><label htmlFor="url">Website URL</label><div className="input-line"><Search size={19}/><input id="url" type="url" placeholder="https://your-website.in" required value={url} onChange={e=>setUrl(e.target.value)} disabled={busy}/><button className="scan-button" type="submit" disabled={busy}><ScanSearch size={19}/>{busy?'Scanning…':'Scan website'} <ArrowRight size={18}/></button></div><div className="options"><div><span>Language</span><select aria-label="Scan language" value={lang} onChange={e=>setLang(e.target.value)} disabled={busy}><option value="both">Hindi + Kannada</option><option value="hi">Hindi / हिन्दी</option><option value="kn">Kannada / ಕನ್ನಡ</option></select></div><label className="check"><input type="checkbox" checked={ai} onChange={e=>setAi(e.target.checked)} disabled={busy||!aiAvailable}/> Suggest & verify fixes with BharatCode AI{!aiAvailable&&<small> (server API key required)</small>}</label></div><div className="examples">Try a public URL: {examples.map((u,i)=><button type="button" key={i} onClick={()=>setUrl(u)} disabled={busy}>{new URL(u).hostname}</button>)}</div></form>}
  {error&&<div className="error"><AlertTriangle size={17}/>{error}</div>}
  {job && !report && <div className="progress"><div className="progress-track"><span/></div><p className="progress-title">Checking your site in Chromium…</p><div className="logs">{job.events.slice(-8).map((x,i)=><p key={i}><span className="log-mark">↳</span> {x}</p>)}</div></div>}
  {report&&<><p className="target">{report.target}</p><div className="summary"><div><strong>{report.summary.error}</strong><span>Errors</span></div><div><strong>{report.summary.warning}</strong><span>Warnings</span></div><div><strong>{report.summary.info}</strong><span>Informational</span></div><a className="report-link" href={asset('report.html')} target="_blank" rel="noreferrer"><FileText size={16}/> Full HTML report <ExternalLink size={15}/></a></div><p className="small-note">All findings come from deterministic browser checks. AI-proposed repairs are labeled verified only after a fresh Chromium recheck.</p><div className="findings"><h3>Findings <span>{report.findings.length}</span></h3>{report.findings.length===0&&<div className="clean-result"><CheckCheck size={24}/> No problems detected by the implemented checks. This does not guarantee rendering is perfect.</div>}
{Array.from(new Set(report.findings.map(f=>f.detector))).map(det=><section className="finding-group" key={det}>
 <h4 className="finding-group-heading">{labels[det]||det}<span>{report.findings.filter(f=>f.detector===det).length}</span></h4>
 {report.findings.filter(f=>f.detector===det).map(f=><article className="issue" key={f.id}>
  <div className="issue-top"><span className={'issue-severity '+f.severity}>{f.severity}</span><strong>{labels[f.detector]||f.detector}</strong><span className="viewport">{(f.viewports||[f.viewport]).map(w=>w+'px').join(' · ')}</span></div>
  <p className="issue-sample">{f.sample||'Font or network resource'}</p>
  <div className="finding-content">
   {(f.element_screenshot||f.screenshot)&&<div className="finding-image"><a href={asset(f.element_screenshot||f.screenshot||'')} target="_blank" rel="noreferrer"><img src={asset(f.element_screenshot||f.screenshot||'')} alt={'Browser screenshot of '+(labels[f.detector]||f.detector)} loading="lazy"/></a><small>Click to examine the browser capture</small></div>}
   <div className="finding-explanation"><p>{f.ai_explanation||'A browser measurement found this issue. AI explanation is unavailable.'}</p>
    {f.fix&&<><p className={'fix-state '+(f.fix.status==='verified'?'pass':'')}>{f.fix.status==='verified'?'✓ Repair verified in browser':f.fix.status==='not-applicable'?'Requires a manual repair':'Repair not verified — '+(f.fix.reason||'Requires review')}</p>
    {(f.fix.css||f.fix.attributes)&&<pre className="fix-diff">{Object.entries({...f.fix.css,...f.fix.attributes}).map(([k,v])=>k+': '+v+';').join('\n')}</pre>}</>}
   </div>
  </div>
  <details><summary>Measured browser evidence</summary><pre>{JSON.stringify(f.evidence,null,2)}</pre><p className="issue-note">{f.url} · {f.selector}</p></details>
 </article>)}
 </section>)}</div></>}
  </section>
  <section id="how" className="how"><div className="how-intro"><span className="eyebrow minor">Our method</span><h2>A careful check.<br/>A repair you can trust.</h2><p>A finding begins with browser evidence. We suggest a repair, run the check again, and show whether it worked.</p></div><div className="steps"><div><span className="stepnum">Inspect</span><ScanSearch size={24}/><h3>Open a real browser</h3><p>Chromium checks actual fonts, letter sequences and layouts at mobile and desktop widths.</p></div><div><span className="stepnum">Correct</span><Code2 size={24}/><h3>Suggest a targeted fix</h3><p>BharatCode Qwen explains verified evidence and drafts a constrained CSS repair.</p></div><div><span className="stepnum">Attest</span><CheckCheck size={24}/><h3>Test it again</h3><p>The repair runs in a fresh browser session. We check the full page again and confirm the original text remains visible.</p></div></div></section>
 </main><footer><span>अ · ಅ &nbsp; AksharaCheck <small>v0.1</small></span><span>Checked carefully, like a school copybook · BharatCode Build League 2026</span></footer></>}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
