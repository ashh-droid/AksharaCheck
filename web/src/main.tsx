import React,{useEffect,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Fix={status:string;css?:Record<string,string>;attributes?:Record<string,string>;reason?:string};
type Finding={id:string;url:string;viewport:number;viewports?:number[];selector:string;sample:string;detector:string;severity:string;evidence:Record<string,unknown>;screenshot?:string;element_screenshot?:string;ai_explanation?:string;fix?:Fix};
type Report={target:string;summary:{error:number;warning:number;info:number};findings:Finding[];pages:{url:string;viewport:number;error?:string}[]};
type Job={status:string;events:string[];error?:string};
type LetterProblem={index:number;title:string;hint:string;character:string};
const API=import.meta.env.VITE_API_URL||'';
const REPO='https://github.com/ashh-droid/AksharaCheck';
const SAMPLE='सूचना: परीक्षा ह िंदी माध्यम में होगी। अाज शाम तक फ़ॉर्म जमा करें।\nಪರೀಕ್ಷೆ ಮುಂದೂಡಲಾಗ ಿದೆ. ಹೊಸ ದಿನಾಂಕವನ್ನು ಶೀಘ್ರದಲ್ಲೇ ತಿಳಿಸಲಾಗುವುದು.';
const detectorNames:Record<string,string>={
 'broken-cluster':'Broken letters','legacy-font':'Legacy encoded fonts','font-load-failed':'Missing web fonts',
 'font-fallback':'Font substitution','possible-clipping':'Cut-off letters','mobile-overflow':'Text beyond the screen',
 'wrong-lang':'Wrong language tag','mixed-language':'Mixed language spans','tight-line-height':'Tight line spacing'
};
const cp=(c:string)=>c.codePointAt(0)||0;
const inside=(c:number,a:number,b:number)=>c>=a&&c<=b;
function kind(ch:string){
 const code=cp(ch);
 if(code===0x200c||code===0x200d)return 'joiner';
 if(inside(code,0x0915,0x0939)||inside(code,0x0958,0x095f)||inside(code,0x0c95,0x0cb9)||code===0x0cde)return 'consonant';
 if(inside(code,0x0904,0x0914)||inside(code,0x0c85,0x0c94))return 'vowel';
 if(code===0x093c||code===0x0cbc)return 'nukta';
 if(code===0x094d||code===0x0ccd)return 'virama';
 if([0x0901,0x0902,0x0903,0x0c81,0x0c82,0x0c83].includes(code))return 'final';
 if(inside(code,0x093e,0x094c)||inside(code,0x0cbe,0x0ccc)||[0x0962,0x0963,0x0ce2,0x0ce3].includes(code))return 'mark';
 return 'other';
}
function script(ch:string){const c=cp(ch);return inside(c,0x0900,0x097f)?'dev':inside(c,0x0c80,0x0cff)?'kan':''}
function checkText(text:string):LetterProblem[]{
 const chars=Array.from(text);const problems:LetterProblem[]=[];
 chars.forEach((ch,i)=>{
  const t=kind(ch);if(!['mark','nukta','virama','final'].includes(t))return;
  const before=chars[i-1]||'';const preceding=kind(before);const scriptMatches=script(before)===script(ch);
  const beforeBefore=chars[i-2]||'';
  const base=scriptMatches&&(preceding==='consonant'||(preceding==='nukta'&&kind(beforeBefore)==='consonant'));
  const hasVowel=preceding==='vowel'||(preceding==='mark'&&scriptMatches);
  let bad=false;
  if(t==='mark'||t==='nukta'||t==='virama')bad=!(base||(t==='mark'&&preceding==='mark'&&(before+ch).normalize('NFC').length===1));
  if(t==='final')bad=!(base||hasVowel);
  if(!bad)return;
  const type=t==='mark'?'vowel sign':t;
  let hint='The '+type+' needs a preceding letter in the same script.';
  if(before===' ')hint='The '+type+' follows a space instead of the letter it belongs to.';
  if(preceding==='vowel'&&t==='mark')hint='Use an independent vowel rather than placing a dependent vowel sign after a vowel.';
  problems.push({index:i,character:ch,title:'◌'+ch+' has nothing to attach to',hint});
 });
 return problems.slice(0,30);
}
function Logo({size=36}:{size?:number}){
 return <svg className="brand-symbol" width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" focusable="false"><path d="M49.65 21.36 A40 40 0 1 1 49.65 98.64" fill="none" stroke="#0E6B4E" strokeWidth="13" strokeLinecap="round"/><circle cx="34.83" cy="91.08" r="6.5" fill="#D9475A"/><circle cx="24.05" cy="77.54" r="6.5" fill="#D9475A"/><circle cx="20" cy="60" r="6.5" fill="#D9475A"/><circle cx="24.05" cy="42.46" r="6.5" fill="#D9475A"/><circle cx="34.83" cy="28.92" r="6.5" fill="#D9475A"/></svg>;
}
function App(){
 const [url,setUrl]=useState('');const [lang,setLang]=useState('both');
 const [ai,setAi]=useState(false);const [aiAvailable,setAiAvailable]=useState(false);
 const [busy,setBusy]=useState(false);const [jobId,setJobId]=useState<string|null>(null);
 const [job,setJob]=useState<Job|null>(null);const [report,setReport]=useState<Report|null>(null);const [error,setError]=useState('');
 const [sample,setSample]=useState(SAMPLE);const [replay,setReplay]=useState(0);
 const input=useRef<HTMLInputElement>(null);const scanSection=useRef<HTMLElement>(null);
 const issues=checkText(sample);
 useEffect(()=>{fetch(API+'/api/health').then(r=>r.json()).then(d=>setAiAvailable(Boolean(d.ai_available))).catch(()=>setAiAvailable(false))},[]);
 useEffect(()=>{
  if(!jobId)return;
  let active=true;let timer:number|undefined;
  const poll=async()=>{
   try{
    const r=await fetch(API+'/api/scans/'+jobId);if(!r.ok)throw Error('This scan is no longer available.');
    const j:Job=await r.json();if(!active)return;setJob(j);
    if(j.status==='running')return;
    if(j.status==='error')throw Error(j.error||'The scan failed.');
    const r2=await fetch(API+'/api/scans/'+jobId+'/report');if(!r2.ok)throw Error('The report could not be loaded.');
    const data:Report=await r2.json();if(!active)return;setReport(data);setBusy(false);setJobId(null);
   }catch(e){if(!active)return;setError(e instanceof Error?e.message:String(e));setBusy(false);setJobId(null)}
  };
  void poll();timer=window.setInterval(()=>void poll(),2000);
  return ()=>{active=false;if(timer!==undefined)window.clearInterval(timer)};
 },[jobId]);
 async function scan(e:React.FormEvent){
  e.preventDefault();setError('');setReport(null);setJob(null);
  let target=url.trim();if(!/^https?:\/\//i.test(target))target='https://'+target;
  try{
   const u=new URL(target);if(!u.hostname.includes('.'))throw Error('Enter a valid public website URL.');
   setUrl(u.href);setBusy(true);
   const response=await fetch(API+'/api/scans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:u.href,lang,use_ai:ai&&aiAvailable})});
   const data=await response.json().catch(()=>({}));if(!response.ok)throw Error(data.detail||'The scan could not be started.');
   setJobId(data.id);
   window.setTimeout(()=>scanSection.current?.scrollIntoView({behavior:'smooth',block:'start'}),50);
  }catch(e){setError(e instanceof Error?e.message:String(e));setBusy(false)}
 }
 const reportArtifact=(file:string)=>API+'/api/scans/'+(reportId.current||'')+'/artifacts/'+encodeURIComponent(file);
 const reportId=useRef<string|null>(null);
 useEffect(()=>{if(jobId)reportId.current=jobId},[jobId]);
 const startOver=()=>{setJobId(null);reportId.current=null;setJob(null);setReport(null);setError('');setBusy(false);input.current?.focus()};
 return <div id="top">
  <a className="skip" href="#main">Skip to content</a>
  <header className="topbar"><div className="wrap topbar-inner">
   <a className="brand" href="#top" aria-label="AksharaCheck home"><Logo size={32}/><span>AksharaCheck</span></a>
   <nav aria-label="Main navigation"><a href="#try">Try it</a><a href="#checks">What it checks</a><a href="#report">Reports</a><a href="#faq">Questions</a><a className="nav-github" href={REPO} target="_blank" rel="noopener noreferrer">GitHub</a></nav>
  </div></header>
  <main id="main">
   <section className="hero wrap">
    <div className="hero-copy">
     <h1>Every letter<br/>should render<br/>right<span className="tiny-green">.</span></h1>
     <p className="lede">Your site may look fine in English. AksharaCheck opens it in a real browser, finds the <span lang="hi">हिंदी</span> and <span lang="kn">ಕನ್ನಡ</span> text that comes out broken, and tests every fix in that same browser before calling it done.</p>
     <form onSubmit={scan} className="scan-form">
      <label htmlFor="url" className="sr-only">Website address</label>
      <div className="scan-input"><input ref={input} id="url" type="text" placeholder="https://your-site.in" value={url} onChange={e=>setUrl(e.target.value)} required spellCheck={false}/><button type="submit" disabled={busy}>{busy?'Checking…':'Check this page'}</button></div>
      <div className="scan-options"><label>Language <select value={lang} onChange={e=>setLang(e.target.value)} disabled={busy}><option value="both">Hindi and Kannada</option><option value="hi">Hindi only</option><option value="kn">Kannada only</option></select></label></div>
      <label className="ai-option"><input type="checkbox" checked={ai} onChange={e=>setAi(e.target.checked)} disabled={!aiAvailable||busy}/> Also suggest CSS fixes with BharatCode AI {!aiAvailable&&<span>(not set up on this server)</span>}</label>
      <p className="examples">Or try <button type="button" onClick={()=>{setUrl('https://hi.wikipedia.org/');input.current?.focus()}}>hi.wikipedia.org</button>, <button type="button" onClick={()=>{setUrl('https://kn.wikipedia.org/');input.current?.focus()}}>kn.wikipedia.org</button> or <button type="button" onClick={()=>{setUrl('https://www.india.gov.in/');input.current?.focus()}}>india.gov.in</button></p>
     </form>
    </div>
    <figure key={replay} className={'copybook hero-sheet anim-'+replay} aria-label="Example rendering problems and verified correction">
     <div className="sheet-top"><span>your-site.in/notices</span><span>390 px</span></div>
     <div className="paper-line"><span className="margin-icon bad">×</span><p lang="hi">परीक्षा <span className="underline-wrong">ह िंदी</span> में होगी</p></div>
     <p className="handnote bad">The ि comes after a space, so it has nothing to attach to. Browsers draw a dotted circle.</p>
     <div className="paper-line"><span className="margin-icon bad">×</span><p lang="kn" className="crop-text">ಪರೀಕ್ಷೆ ಮುಂದೂಡಲಾಗಿದೆ</p></div>
     <p className="handnote bad"><code>line-height: 1</code> and <code>overflow: hidden</code> can cut the tops off letters.</p>
     <div className="paper-line"><span className="margin-icon good">✓</span><p lang="kn" className="good">ಪರೀಕ್ಷೆ ಮುಂದೂಡಲಾಗಿದೆ</p></div>
     <p className="handnote good">With <code>line-height: 1.6</code> the whole letter shows. Rechecked at phone and desktop width.</p>
     <div className="verified-stamp"><span>✓</span><small>VERIFIED IN BROWSER</small></div>
     <button className="play-again" type="button" onClick={()=>setReplay(v=>v+1)}>Play again</button>
    </figure>
   </section>
   <section ref={scanSection} id="scan" className="live-results wrap" hidden={!busy&&!report&&!error}>
    <div className="scan-result-head"><div><p className="eyebrow">{busy?'Checking':'Scan report'}</p><h2>{busy?'Opening the page in Chromium':error?'The scan could not finish':report?.findings.length+' findings recorded'}</h2></div><button type="button" className="quiet-button" onClick={startOver}>Check another page</button></div>
    {error&&<p className="error-message" role="alert">{error}</p>}
    {busy&&<div role="status" className="scan-progress"><p>Checking mobile and desktop rendering.</p>{job?.events?.slice(-6).map((e,i)=><p key={i} className="progress-line">{e}</p>)}</div>}
    {report&&<div className="audit"><p className="audit-target">{report.target}</p><div className="audit-summary"><span>{report.summary.error} errors</span><span>{report.summary.warning} warnings</span><span>{report.summary.info} notes</span><a href={reportArtifact('report.html')} target="_blank" rel="noreferrer">Open full report</a></div>{report.pages.some(p=>p.error)&&<p className="error-message">Some pages or widths could not be scanned. These are not counted as clean.</p>}
      {!report.findings.length&&<p className="clean-result">No issues were detected by the implemented checks. This is not proof of complete correctness.</p>}
      {Array.from(new Set(report.findings.map(f=>f.detector))).map(type=><div className="audit-group" key={type}><h3>{detectorNames[type]||type} <span>{report.findings.filter(f=>f.detector===type).length}</span></h3>
       {report.findings.filter(f=>f.detector===type).map(f=><article className="audit-card" key={f.id}>
        <header><span className={'audit-severity '+f.severity}>{f.severity}</span><strong>{detectorNames[f.detector]||f.detector}</strong><small>{(f.viewports||[f.viewport]).map(w=>w+' px').join(' / ')}</small></header>
        <p className="audit-sample">{f.sample}</p><div className="audit-card-content">
         {(f.element_screenshot||f.screenshot)&&<a href={reportArtifact(f.element_screenshot||f.screenshot||'')} target="_blank" rel="noreferrer"><img src={reportArtifact(f.element_screenshot||f.screenshot||'')} alt={'Browser capture for '+f.detector}/></a>}
         <div><p>{f.ai_explanation||'This finding comes from the browser measurement.'}</p>{f.fix&&<p className={f.fix.status==='verified'?'verified-note':'unverified-note'}>{f.fix.status==='verified'?'✓ Fix verified in Chromium':f.fix.status==='not-applicable'?'Manual repair needed':'Not verified: '+(f.fix.reason||'Review the change')}</p>}{(f.fix?.css||f.fix?.attributes)&&<pre>{Object.entries({...f.fix.css,...f.fix.attributes}).map(([k,v])=>k+': '+v+';').join('\n')}</pre>}</div></div>
        <details><summary>Measured evidence</summary><pre>{JSON.stringify(f.evidence,null,2)}</pre><p className="audit-target">{f.url}</p></details>
       </article>)}</div>)}
      </div>}
   </section>
   <section className="try-section" id="try"><div className="wrap">
    <div className="section-head"><h2>Check a line of text right here</h2><p>Paste Hindi or Kannada text and the letter rules run as you type. It all happens in your browser, so nothing is uploaded.</p></div>
    <div className="try-grid">
     <div className="copybook text-editor"><div className="sheet-top"><span>Your text</span><button type="button" onClick={()=>setSample(SAMPLE)}>Load the example</button></div><textarea aria-label="Hindi or Kannada text to check" spellCheck={false} value={sample} onChange={e=>setSample(e.target.value)}/></div>
     <div className="try-feedback"><h3 className={issues.length?'red-text':'green-text'}>{issues.length?'× '+issues.length+' broken '+(issues.length===1?'letter':'letters'):sample.trim()?'✓ No broken letters found':'Paste text to check it'}</h3>
      <p className="rendered-sample">{Array.from(sample).map((ch,i)=><React.Fragment key={i}>{issues.some(x=>x.index===i)?<span className="underline-wrong">{ch}</span>:ch}</React.Fragment>)}</p>
      <ol>{issues.map((issue,i)=><li key={i}><strong>{issue.title}</strong> <code>{'U+'+cp(issue.character).toString(16).toUpperCase().padStart(4,'0')}</code><p>{issue.hint}</p></li>)}</ol>
     </div>
    </div></div></section>
   <section className="checks-section wrap" id="checks"><div className="section-head"><h2>What it checks</h2><p>Four problems that make Hindi and Kannada pages hard to read. Each one is measured in Chromium at phone and desktop widths.</p></div>
    <div className="checks-grid">
     <article className="check-card"><div className="rule-preview" lang="hi"><span className="underline-wrong">ह िंदी</span></div><h3>Broken letters</h3><p>A vowel sign, virama or nukta with nothing to attach to. Browsers draw it on a dotted circle.</p></article>
     <article className="check-card"><div className="rule-preview"><span className="tofu">□□□□</span></div><h3>Missing fonts</h3><p>Chromium reports which font drew each letter, so it can reveal unexpected fallback or empty boxes.</p></article>
     <article className="check-card"><div className="rule-preview" lang="kn"><span className="crop-text">ಪರೀಕ್ಷೆ</span></div><h3>Cut-off letters</h3><p>A tight line height or hidden overflow can cut letters above or below the line.</p></article>
     <article className="check-card"><div className="rule-preview code-preview"><code>&lt;html lang=<span className="underline-wrong">"en"</span>&gt;</code></div><h3>Wrong language tag</h3><p>Hindi marked as English can be misread by assistive technology and may use a different font.</p></article>
    </div>
   </section>
   <section className="report-section" id="report"><div className="wrap"><div className="section-head"><h2>Every finding comes with its evidence</h2><p>Each finding shows what broke, where it is on the page and what the browser measured, so a developer can go straight to the fix.</p></div>
    <div className="report-grid">
     <article className="sample-report">
      <div className="sample-report-top"><span>× Error</span><strong>Broken letter</strong><small>390 px</small></div>
      <p className="sample-report-word" lang="hi">सूचना: परीक्षा <span className="underline-wrong">ह िंदी</span> माध्यम में होगी</p>
      <div className="sample-evidence"><p><span>Characters</span><code>ह U+0939</code> <code>space U+0020</code> <code>ि U+093F</code></p><p><span>Rule</span>A vowel sign must follow a consonant.</p><p><span>Element</span><code>main &gt; article p:nth-of-type(2)</code></p><p><span>Font</span>Mukta, the page's own web font</p></div>
      <div className="sample-fix"><strong>Suggested fix</strong><p>Remove the space between ह and ि in the page text. This is a typing mistake, so CSS cannot fix it and none is suggested.</p></div>
     </article>
     <div className="report-notes"><div><h3>The exact characters</h3><p>Each finding lists the Unicode code points, so you can search for the mistake in your CMS or code.</p></div><div><h3>CSS only where CSS helps</h3><p>BharatCode AI drafts CSS for layout and font problems. A typing mistake is reported as a typing mistake.</p></div><div><h3>Every fix is tested</h3><p>The change runs in a fresh browser. If it hides the text, shrinks it or pushes it off screen, it is rejected.</p></div></div>
    </div>
   </div></section>
   <section className="faq-section wrap" id="faq"><h2>Questions</h2><div className="faq-list">
    <details><summary>Does AksharaCheck change my website?</summary><p>No. It only reads a public page. Suggested fixes are tested in a separate browser session, not committed to your website.</p></details>
    <details><summary>Which languages does it support?</summary><p>Hindi and Kannada. The rules also recognize other languages written in the Devanagari and Kannada scripts, including Marathi, Nepali, Sanskrit and Tulu.</p></details>
    <details><summary>Do I need the AI to use it?</summary><p>No. Browser detectors generate findings without AI. BharatCode AI is optional for explanations and repair suggestions.</p></details>
    <details><summary>Can it check pages behind a login?</summary><p>Not yet. It checks public pages only. Local and private network addresses are not supported by the hosted scanner.</p></details>
    <details><summary>Is it open source?</summary><p>Yes. The scanner, rules, and website source are available in the <a href={REPO} target="_blank" rel="noreferrer">GitHub repository</a>.</p></details>
   </div></section>
   <section className="bottom-cta wrap"><Logo size={46}/><h2>Find the broken letters before<br/>your readers do.</h2><a href="#top">Check a page</a></section>
  </main>
  <footer className="footer wrap"><div className="footer-brand"><Logo size={22}/><strong>AksharaCheck</strong><span lang="hi">अक्षर जाँच</span><span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span></div><div><a href={REPO} target="_blank" rel="noreferrer">GitHub</a><a href="https://bharatcode.ai/hackathon" target="_blank" rel="noreferrer">BharatCode Build League 2026</a></div></footer>
 </div>
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
