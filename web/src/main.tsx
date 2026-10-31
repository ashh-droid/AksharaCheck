import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource-variable/anek-latin/wght.css';
import '@fontsource-variable/anek-devanagari/wght.css';
import '@fontsource-variable/anek-kannada/wght.css';
import './style.css';
import { checkText, codepoint, LetterProblem } from './letters';

/* ---------- Types shared with the Python report.json ---------- */

type Attempt = { css?: Record<string, string>; attributes?: Record<string, string>; status: string; reason?: string };
type Fix = {
  status: string;
  css?: Record<string, string>;
  attributes?: Record<string, string>;
  reason?: string;
  viewport?: number;
  after_screenshot?: string;
  attempts?: Attempt[];
};
type Finding = {
  id: string;
  url: string;
  viewport: number;
  viewports?: number[];
  selector: string;
  sample: string;
  detector: string;
  severity: 'error' | 'warning' | 'info' | string;
  evidence: Record<string, unknown>;
  screenshot?: string;
  element_screenshot?: string;
  ai_explanation?: string | null;
  summary_hi?: string;
  summary_kn?: string;
  fix?: Fix | null;
};
type Report = {
  target: string;
  summary: { error: number; warning: number; info: number };
  findings: Finding[];
  pages: { url: string; viewport: number; error?: string }[];
  ai?: { model?: string; calls?: number; input_tokens?: number; output_tokens?: number; seconds?: number };
};
type Job = { status: string; events: string[]; error?: string };
type RecordedScan = {
  slug: string;
  kind?: 'fixture' | 'public';
  title: string;
  target: string;
  scanned_at: string;
  counts?: { error?: number; warning?: number; info?: number };
  ai_calls?: number;
  verified_fixes?: number;
  ai_explained?: number;
  ai_eligible?: number;
  review_note?: string;
  highlight?: { title?: string; sample?: string };
};

/* ---------- Icons ----------
   Drawn shapes, not ✓ ✗ ↗ characters: Anek has no such glyphs, so Windows
   substitutes a symbol font and draws them in a different style. */

const ICONS = { check: 'M3 8.5l3.2 3.2L13 4.8', cross: 'M4 4l8 8M12 4l-8 8', out: 'M5.5 10.5l5-5M6.5 5.5h4v4' } as const;
function Icon({ name }: { name: keyof typeof ICONS }) {
  return (
    <svg className={'ico ico-' + name} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
      <path d={ICONS[name]} />
    </svg>
  );
}

/* ---------- Settings ---------- */

const API = import.meta.env.VITE_API_URL || '';
// On GitHub Pages there is no scanner service unless VITE_API_URL is set at build time.
const PAGES_PREVIEW = window.location.hostname.endsWith('.github.io') && !import.meta.env.VITE_API_URL;
const REPO = 'https://github.com/ashh-droid/AksharaCheck';
const BASE = import.meta.env.BASE_URL;
const COMMANDS = [
  'git clone https://github.com/ashh-droid/AksharaCheck.git',
  'cd AksharaCheck',
  'py -3 -m venv .venv',
  '.venv\\Scripts\\python.exe -m pip install -e .',
  '.venv\\Scripts\\python.exe -m playwright install chromium',
  '.venv\\Scripts\\python.exe -m aksharacheck scan https://your-site.in --lang both --output output',
];
const recordedReportUrl = (slug: string) => BASE + 'samples/' + encodeURIComponent(slug) + '/report.html';

const SEVERITY: Record<string, { word: string; band: string }> = {
  error: { word: 'Fix', band: 'To fix' },
  warning: { word: 'Check', band: 'To check' },
  info: { word: 'Note', band: 'Notes' },
};
const DETECTOR_NAMES: Record<string, string> = {
  'broken-cluster': 'Broken letters',
  'possible-clipping': 'Letters may be cut off',
  'mobile-overflow': 'Text runs off the screen on phones',
  'wrong-lang': 'Wrong language tag',
  'mixed-language': 'Two languages without labels',
  'font-load-failed': 'Web font did not load',
  'font-fallback': 'A different font was used',
  'legacy-font': 'Old non-Unicode font',
  'tight-line-height': 'Tight line spacing',
};

const BROKEN_SAMPLE = 'सूचना: परीक्षा ह िंदी माध्यम में होगी। अाज शाम तक फ़ॉर्म जमा करें।\nಪರೀಕ್ಷೆ ಮುಂದೂಡಲಾಗ ಿದೆ. ಹೊಸ ದಿನಾಂಕವನ್ನು ಶೀಘ್ರದಲ್ಲೇ ತಿಳಿಸಲಾಗುವುದು.';
const CLEAN_SAMPLE = 'सूचना: परीक्षा हिंदी माध्यम में होगी। आज शाम तक फ़ॉर्म जमा करें।\nಪರೀಕ್ಷೆ ಮುಂದೂಡಲಾಗಿದೆ. ಹೊಸ ದಿನಾಂಕವನ್ನು ಶೀಘ್ರದಲ್ಲೇ ತಿಳಿಸಲಾಗುವುದು.';

const plural = (n: number, one: string, many = one + 's') => `${n.toLocaleString('en-IN')} ${n === 1 ? one : many}`;
const cssText = (change?: { css?: Record<string, string>; attributes?: Record<string, string> }) =>
  [
    ...Object.entries(change?.css || {}).map(([k, v]) => `${k}: ${v};`),
    ...Object.entries(change?.attributes || {}).map(([k, v]) => `${k}="${v}"`),
  ].join(' ');
const widthName = (w: number) => (w <= 430 ? 'phone' : w <= 1024 ? 'tablet' : 'desktop');
const scanDate = (iso: string) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};
const hostOf = (url: string) => {
  try {
    const u = new URL(url);
    return (u.host + u.pathname.replace(/\/$/, '')).replace(/^www\./, '');
  } catch {
    return url;
  }
};
const langOf = (text: string) => {
  let deva = 0;
  let kan = 0;
  for (const ch of text) {
    const c = codepoint(ch);
    if (c >= 0x0900 && c <= 0x097f) deva++;
    if (c >= 0x0c80 && c <= 0x0cff) kan++;
  }
  return deva === 0 && kan === 0 ? undefined : deva >= kan ? 'hi' : 'kn';
};
function summarySentence(counts: { error?: number; warning?: number; info?: number }) {
  const parts: string[] = [];
  if (counts.error) parts.push(plural(counts.error, 'problem') + ' to fix');
  if (counts.warning) parts.push(plural(counts.warning, 'thing') + ' to check');
  if (counts.info) parts.push(plural(counts.info, 'note'));
  if (!parts.length) return 'Nothing broke in these checks.';
  const text = parts.length === 1 ? parts[0] : parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1];
  return text[0].toUpperCase() + text.slice(1) + '.';
}

/* ---------- Small pieces ---------- */

function Logo({ size = 32, onDark = false }: { size?: number; onDark?: boolean }) {
  const arc = onDark ? '#3FB58A' : '#0E6B4E';
  const dot = onDark ? '#F07A88' : '#D9475A';
  return (
    <svg className="logo" width={size} height={size} viewBox="0 0 120 120" aria-hidden="true" focusable="false">
      <path d="M49.65 21.36 A40 40 0 1 1 49.65 98.64" fill="none" stroke={arc} strokeWidth="13" strokeLinecap="round" />
      {[
        [34.83, 91.08],
        [24.05, 77.54],
        [20, 60],
        [24.05, 42.46],
        [34.83, 28.92],
      ].map(([cx, cy]) => (
        <circle key={cx + '-' + cy} cx={cx} cy={cy} r="6.5" fill={dot} />
      ))}
    </svg>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="copy"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1600);
        } catch {
          setCopied(false);
        }
      }}
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

/* ---------- Header ---------- */

function Header() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  const links = [
    ['#reports', 'Reports'],
    ['#how', 'How it works'],
    ['#try', 'Try it'],
    ['#run', 'Run it'],
    ['#faq', 'Questions'],
  ];
  return (
    <header className={'topbar' + (scrolled ? ' is-scrolled' : '')}>
      <div className="wrap topbar-inner">
        <a className="brand" href="#top" aria-label="AksharaCheck, back to top" onClick={() => setOpen(false)}>
          <Logo size={46} />
          <span className="brand-text">
            <span className="brand-name">AksharaCheck</span>
            <span className="brand-sub">
              <span lang="hi">अक्षर जाँच</span>
              <span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span>
            </span>
          </span>
        </a>
        <button
          className="menu-toggle"
          type="button"
          aria-controls="site-menu"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="menu-icon" aria-hidden="true" data-open={open} />
          <span>{open ? 'Close' : 'Menu'}</span>
        </button>
        <nav id="site-menu" className={open ? 'is-open' : ''} aria-label="Main navigation">
          {links.map(([href, label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)}>
              {label}
            </a>
          ))}
          <a href={REPO} target="_blank" rel="noopener noreferrer">
            GitHub <Icon name="out" />
          </a>
        </nav>
      </div>
    </header>
  );
}

/* ---------- Hero: a repair as it actually happens ---------- */

function RepairDemo() {
  const [run, setRun] = useState(0);
  const d = (seconds: number) => ({ '--d': seconds + 's' }) as React.CSSProperties;
  return (
    <figure key={run} className="demo" aria-label="Example: cut-off Kannada letters, the repairs BharatCode suggested, and the one Chromium accepted">
      <div className="demo-glyphs" lang="kn">
        <span className="glyph-before">
          <span className="cut">ಪರೀಕ್ಷೆ</span>
        </span>
        <svg className="glyph-arrow step" style={d(0.5)} viewBox="0 0 64 24" aria-hidden="true">
          <path d="M2 12h56m-10-9 10 9-10 9" />
        </svg>
        <span className="glyph-after step" style={d(2.6)}>
          ಪರೀಕ್ಷೆ
        </span>
      </div>
      <div className="demo-trail">
        <p className="demo-head step" style={d(0.2)}>
          <span className="sev warning">Check</span> Letters cut off at 390 px
        </p>
        <p className="demo-ai step" style={d(0.8)}>
          <span className="demo-who">BharatCode</span>
          The heading has a fixed height and hides its overflow, so the vowel signs are cut off.
        </p>
        <ol className="demo-tries" aria-label="Repairs tested in Chromium">
          <li className="bad step" style={d(1.5)}>
            <span className="mark">
              <Icon name="cross" />
            </span>
            <code>height: 1px</code>
            <span>Rejected: text area shrank</span>
          </li>
          <li className="ok step" style={d(2.2)}>
            <span className="mark">
              <Icon name="check" />
            </span>
            <code>height: auto; line-height: 1.7</code>
            <span>Verified in Chromium</span>
          </li>
        </ol>
      </div>
      <figcaption className="demo-caption">
        <span>Example finding</span>
        <button type="button" onClick={() => setRun((v) => v + 1)}>
          Play again
        </button>
      </figcaption>
    </figure>
  );
}

/* ---------- Live scanning (only when a scanner service is connected) ---------- */

function ScanForm({
  onStart,
  busy,
  aiAvailable,
  online,
}: {
  onStart: (url: string, lang: string, ai: boolean) => void;
  busy: boolean;
  aiAvailable: boolean;
  online: boolean | null;
}) {
  const [url, setUrl] = useState('');
  const [lang, setLang] = useState('both');
  const [ai, setAi] = useState(true);
  const [problem, setProblem] = useState('');
  const field = useRef<HTMLInputElement>(null);
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    let target = url.trim();
    if (!target) {
      setProblem('Enter a web address, like https://your-site.in');
      return;
    }
    if (!/^https?:\/\//i.test(target)) target = 'https://' + target;
    try {
      const u = new URL(target);
      if (!u.hostname.includes('.')) throw new Error();
      setProblem('');
      setUrl(u.href);
      onStart(u.href, lang, ai && aiAvailable);
    } catch {
      setProblem('Enter a full web address, like https://your-site.in');
    }
  };
  return (
    <form className="scan-form" onSubmit={submit} noValidate>
      <label htmlFor="url" className="sr-only">
        Page address
      </label>
      <div className="scan-row">
        <input
          ref={field}
          id="url"
          type="url"
          inputMode="url"
          placeholder="https://your-site.in"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          spellCheck={false}
          aria-invalid={problem ? true : undefined}
          aria-describedby={problem ? 'url-problem' : undefined}
        />
        <button className="btn primary" type="submit" disabled={busy}>
          {busy ? 'Checking…' : 'Check this page'}
        </button>
      </div>
      {problem && (
        <p id="url-problem" className="form-problem">
          {problem}
        </p>
      )}
      <div className="scan-options">
        <label className="field">
          <span>Language</span>
          <select value={lang} onChange={(e) => setLang(e.target.value)} disabled={busy}>
            <option value="both">Hindi and Kannada</option>
            <option value="hi">Hindi</option>
            <option value="kn">Kannada</option>
          </select>
        </label>
        {aiAvailable && (
          <label className="check">
            <input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} disabled={busy} />
            <span>Explain and fix with BharatCode</span>
          </label>
        )}
      </div>
      {online === false && <p className="form-note">The scanner service is not reachable right now. The text checker below still works.</p>}
      <p className="examples">
        Or try{' '}
        {['hi.wikipedia.org', 'kn.wikipedia.org'].map((site, i) => (
          <React.Fragment key={site}>
            {i > 0 && ' or '}
            <button
              type="button"
              onClick={() => {
                setUrl('https://' + site + '/');
                field.current?.focus();
              }}
            >
              {site}
            </button>
          </React.Fragment>
        ))}
      </p>
    </form>
  );
}

function FindingCard({ f, asset }: { f: Finding; asset: (name: string) => string }) {
  const sev = SEVERITY[f.severity] ? f.severity : 'info';
  const fix = f.fix || undefined;
  const before = f.element_screenshot;
  const after = fix?.status === 'verified' ? fix.after_screenshot : undefined;
  const sequences = ((f.evidence?.invalid_sequences as { sequence?: string; codepoints?: string[]; reason?: string }[]) || []).slice(0, 6);
  return (
    <article className={'finding ' + sev}>
      <div className="finding-main">
        <p className="finding-top">
          <span className={'sev ' + sev}>{SEVERITY[sev].word}</span>
          <strong>{DETECTOR_NAMES[f.detector] || f.detector}</strong>
          <span className="muted">{[...new Set((f.viewports || [f.viewport]).map(widthName))].join(' and ')}</span>
        </p>
        {f.sample && (
          <p className="finding-sample" lang={langOf(f.sample)}>
            {f.sample}
          </p>
        )}
        {sequences.length > 0 && (
          <ul className="sequences">
            {sequences.map((s, i) => (
              <li key={i}>
                <span className="glyph" lang={langOf(s.sequence || '')}>
                  {(s.sequence || '').trim()}
                </span>
                <code>{(s.codepoints || []).join(' ')}</code>
              </li>
            ))}
          </ul>
        )}
        {f.ai_explanation && (
          <div className="ai">
            <p className="ai-label">What BharatCode says</p>
            <p>{f.ai_explanation}</p>
            {f.summary_hi && (
              <p className="translation">
                <span className="lang-name" lang="hi">
                  हिंदी
                </span>
                <span lang="hi">{f.summary_hi}</span>
              </p>
            )}
            {f.summary_kn && (
              <p className="translation">
                <span className="lang-name" lang="kn">
                  ಕನ್ನಡ
                </span>
                <span lang="kn">{f.summary_kn}</span>
              </p>
            )}
          </div>
        )}
        {fix?.status === 'verified' && (
          <div className="repair ok">
            <p className="repair-title">
              <Icon name="check" /> Fix ready, tested in Chromium at {fix.viewport || f.viewport} px
            </p>
            <pre>{cssText(fix).replace(/; /g, ';\n')}</pre>
          </div>
        )}
        {fix?.status === 'unverified' && (
          <div className="repair bad">
            <p className="repair-title">
              <Icon name="cross" /> No suggested fix passed. {fix.reason}
            </p>
          </div>
        )}
        {(fix?.attempts?.length || 0) > 1 && (
          <ol className="tries">
            {fix!.attempts!.map((a, i) => (
              <li key={i} className={a.status === 'verified' ? 'ok' : 'bad'}>
                <span className="mark">
                  <Icon name={a.status === 'verified' ? 'check' : 'cross'} />
                </span>
                <code>{cssText(a)}</code>
                <span>{a.status === 'verified' ? 'Passed' : 'Rejected: ' + (a.reason || 'did not pass')}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
      {(before || after) && (
        <div className="finding-shots">
          {before && (
            <figure>
              <img src={asset(before)} alt="The element as Chromium drew it" />
              <figcaption>{after ? 'Before' : 'As Chromium drew it'}</figcaption>
            </figure>
          )}
          {after && (
            <figure>
              <img src={asset(after)} alt="The element after the fix" />
              <figcaption>After</figcaption>
            </figure>
          )}
        </div>
      )}
    </article>
  );
}

function LiveResults({
  busy,
  job,
  report,
  error,
  scanId,
  onReset,
}: {
  busy: boolean;
  job: Job | null;
  report: Report | null;
  error: string;
  scanId: string | null;
  onReset: () => void;
}) {
  const asset = (name: string) => API + '/api/scans/' + scanId + '/artifacts/' + encodeURIComponent(name);
  const order = ['error', 'warning', 'info'];
  return (
    <section id="scan" className="wrap live" aria-live="polite">
      <div className="live-head">
        <div>
          <p className="kicker">{busy ? 'Checking' : error ? 'Scan stopped' : 'Scan finished'}</p>
          <h2>{busy ? 'Opening the page in Chromium' : error ? 'The page could not be checked' : report ? hostOf(report.target) : ''}</h2>
          {report && <p className="live-summary">{summarySentence(report.summary)}</p>}
        </div>
        <div className="live-actions">
          {report && scanId && (
            <a className="btn secondary" href={asset('report.html')} target="_blank" rel="noopener noreferrer">
              Open full report
            </a>
          )}
          <button type="button" className="btn quiet" onClick={onReset}>
            Check another page
          </button>
        </div>
      </div>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {busy && (
        <div className="progress" role="status">
          <p className="progress-title">Checking the page at phone and desktop widths…</p>
          {job?.events?.slice(-6).map((line, i) => (
            <p key={i} className="progress-line">
              {line}
            </p>
          ))}
        </div>
      )}
      {report && (
        <>
          {report.pages.some((p) => p.error) && <p className="alert">Some pages or widths could not be checked. They are not counted as clean.</p>}
          {!report.findings.length && <p className="clean">
              <Icon name="check" /> Nothing broke on this page at these widths.
            </p>}
          {order.map((sev) => {
            const items = report.findings.filter((f) => (SEVERITY[f.severity] ? f.severity : 'info') === sev);
            if (!items.length) return null;
            return (
              <div key={sev} className="band">
                <h3>
                  {SEVERITY[sev].band} <span>{items.length}</span>
                </h3>
                {items.map((f) => (
                  <FindingCard key={f.id} f={f} asset={asset} />
                ))}
              </div>
            );
          })}
        </>
      )}
    </section>
  );
}

/* ---------- Recorded scans ---------- */

function RecordedScans({ scans }: { scans: RecordedScan[] }) {
  if (!scans.length) return null;
  return (
    <div className="recorded" id="recorded">
      <div className="recorded-head">
        <h3>Explore recorded reports</h3>
        <p>Controlled BharatCode demonstration and real public-page scans. These are dated browser snapshots, not full accessibility certifications.</p>
      </div>
      <div className="recorded-grid">
        {scans.map((s) => {
          const fixture = s.kind === 'fixture';
          const counts = s.counts || {};
          const pills = [
            ['error', counts.error, plural(counts.error || 0, 'to fix', 'to fix')],
            ['warning', counts.warning, plural(counts.warning || 0, 'to check', 'to check')],
            ['info', counts.info, plural(counts.info || 0, 'note')],
          ].filter(([, n]) => n) as [string, number, string][];
          const explained = s.ai_explained || 0;
          const stat = fixture
            ? (explained ? `BharatCode explained ${explained} of ${s.ai_eligible || explained}` : '') +
              ((s.verified_fixes || 0) > 0 ? (explained ? ' · ' : '') + plural(s.verified_fixes || 0, 'fix', 'fixes') + ' verified in Chromium' : '')
            : (counts.error || counts.warning)
              ? 'Browser-only scan · findings require manual review'
              : counts.info
                ? 'Browser-only scan · informational observations, not confirmed defects'
                : '';
          return (
            <a key={s.slug} className={'recorded-card ' + (fixture ? 'fixture' : 'public')} href={recordedReportUrl(s.slug)} target="_blank" rel="noopener noreferrer">
              <span className="recorded-kind">{fixture ? 'BharatCode demonstration' : 'Public website'}</span>
              <span className="recorded-site">{s.title}</span>
              <span className="recorded-url">{fixture ? 'Test page with planted rendering bugs' : hostOf(s.target)}</span>
              {s.highlight?.sample ? (
                <span className="recorded-sample" lang={langOf(s.highlight.sample)}>
                  {s.highlight.sample}
                </span>
              ) : !counts.error && !counts.warning && !counts.info ? (
                <span className="recorded-sample recorded-clean">
                  <Icon name="check" /> No findings in the recorded scan at its tested widths.
                </span>
              ) : null}
              <span className="recorded-counts">
                {pills.length ? (
                  pills.map(([kind, n, label]) => (
                    <span key={kind} className={'sev ' + kind}>
                      {kind === 'info' ? label : n + ' ' + label.replace(/^\d+ /, '')}
                    </span>
                  ))
                ) : (
                  <span className="sev info">0 findings</span>
                )}
              </span>
              {stat && <span className="recorded-stat">{stat}</span>}
              {s.review_note && <span className="recorded-review">{s.review_note}</span>}
              <span className="recorded-foot">
                <span>Scanned {scanDate(s.scanned_at)}</span>
                <span className="recorded-open">
                  Open report <Icon name="out" />
                </span>
              </span>
            </a>
          );
        })}
      </div>
    </div>
  );
}

/* ---------- Text checker ---------- */

function TextChecker() {
  const [text, setText] = useState(BROKEN_SAMPLE);
  const [note, setNote] = useState('');
  const box = useRef<HTMLTextAreaElement>(null);
  const problems = useMemo(() => checkText(text), [text]);
  const chars = useMemo(() => Array.from(text), [text]);
  const marked = useMemo(() => {
    // Mark the broken sign with the letter before it, and keep any marks that follow
    // inside the same span, so the numbering never splits a cluster.
    const out: React.ReactNode[] = [];
    let cursor = 0;
    problems.forEach((p: LetterProblem, n: number) => {
      const from = Math.max(p.index - 1, cursor);
      let end = p.index + 1;
      while (end < chars.length && /\p{M}/u.test(chars[end])) end++;
      if (from > cursor) out.push(chars.slice(cursor, from).join(''));
      out.push(
        <span key={'m' + n} className="wavy">
          {chars.slice(from, end).join('')}
        </span>,
        <sup key={'s' + n}>{n + 1}</sup>,
      );
      cursor = end;
    });
    if (cursor < chars.length) out.push(chars.slice(cursor).join(''));
    return out;
  }, [problems, chars]);
  const broken = text === BROKEN_SAMPLE;
  return (
    <section className="try" id="try" aria-labelledby="try-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="try-title">Check a line of text right here</h2>
          <p>Paste Hindi or Kannada text and the letter rules run as you type. It all happens in your browser, so nothing is uploaded.</p>
        </div>
        <div className="try-grid">
          <div className="sheet editor">
            <div className="sheet-head">
              <label htmlFor="sample">Your text</label>
              <button
                type="button"
                className="link"
                onClick={() => {
                  const next = broken ? CLEAN_SAMPLE : BROKEN_SAMPLE;
                  setText(next);
                  setNote(next === BROKEN_SAMPLE ? 'Broken example loaded.' : 'Clean example loaded.');
                  box.current?.focus();
                }}
              >
                {broken ? 'Show the corrected text' : 'Show the broken example'}
              </button>
            </div>
            <textarea
              id="sample"
              ref={box}
              value={text}
              spellCheck={false}
              placeholder="Paste or type Hindi or Kannada text"
              onChange={(e) => {
                setText(e.target.value);
                setNote('');
              }}
            />
            <p className="sheet-foot" role="status">
              {note || 'Checked in this browser. Nothing is uploaded.'}
            </p>
          </div>
          <div className="try-out">
            <p className={'verdict ' + (problems.length ? 'bad' : text.trim() ? 'ok' : '')} aria-live="polite">
              {problems.length ? (
                <>
                  <Icon name="cross" /> {plural(problems.length, 'broken letter')}
                </>
              ) : text.trim() ? (
                <>
                  <Icon name="check" /> No broken letters found
                </>
              ) : (
                'Results appear here'
              )}
            </p>
            {text.trim() && <p className="rendered">{marked}</p>}
            {problems.length > 0 && (
              <ol className="problems">
                {problems.map((p, i) => (
                  <li key={i}>
                    <strong>{p.title}</strong> <code>{'U+' + codepoint(p.character).toString(16).toUpperCase().padStart(4, '0')}</code>
                    <span>{p.hint}</span>
                  </li>
                ))}
              </ol>
            )}
            <p className="fine">This checks letter sequences only. Fonts, layout and cut-off letters need the page scan.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

/* ---------- Page ---------- */

function App() {
  const [scans, setScans] = useState<RecordedScan[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);
  const [aiAvailable, setAiAvailable] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scanId, setScanId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState('');
  const resultsShown = busy || !!report || !!error;

  useEffect(() => {
    fetch(BASE + 'samples/catalog.json')
      .then((r) => (r.ok ? r.json() : { scans: [] }))
      .then((d) =>
        setScans(
          Array.isArray(d.scans)
            ? d.scans.filter((s: RecordedScan) => typeof s.slug === 'string' && /^[a-z0-9-]+$/.test(s.slug) && typeof s.title === 'string')
            : [],
        ),
      )
      .catch(() => setScans([]));
  }, []);

  useEffect(() => {
    // GitHub Pages has no scanner endpoint, so do not ask for one.
    if (PAGES_PREVIEW) return;
    fetch(API + '/api/health')
      .then((r) => {
        if (!r.ok) throw new Error();
        return r.json();
      })
      .then((d) => {
        setOnline(true);
        setAiAvailable(Boolean(d.ai_available));
      })
      .catch(() => setOnline(false));
  }, []);

  useEffect(() => {
    if (!scanId || !busy) return;
    let active = true;
    const poll = async () => {
      try {
        const r = await fetch(API + '/api/scans/' + scanId);
        if (!r.ok) throw new Error('This scan is no longer available. Start a new one.');
        const j: Job = await r.json();
        if (!active) return;
        setJob(j);
        if (j.status === 'running') return;
        if (j.status === 'error') throw new Error(j.error || 'The scan failed.');
        const r2 = await fetch(API + '/api/scans/' + scanId + '/report');
        if (!r2.ok) throw new Error('The scan finished, but the report could not be loaded.');
        const data: Report = await r2.json();
        if (!active) return;
        setReport(data);
        setBusy(false);
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : String(e));
        setBusy(false);
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), 2000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [scanId, busy]);

  const start = async (url: string, lang: string, ai: boolean) => {
    setError('');
    setReport(null);
    setJob(null);
    setBusy(true);
    window.setTimeout(() => document.getElementById('scan')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60);
    try {
      const r = await fetch(API + '/api/scans', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, lang, use_ai: ai }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'The scan could not start (HTTP ' + r.status + ').');
      if (!d.id) throw new Error('The scanner did not return a scan ID.');
      setScanId(d.id);
    } catch (e) {
      setOnline(e instanceof TypeError ? false : online);
      setError(e instanceof TypeError ? 'The scanner service is not reachable right now.' : e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };
  const reset = () => {
    setBusy(false);
    setScanId(null);
    setJob(null);
    setReport(null);
    setError('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    window.setTimeout(() => document.getElementById('url')?.focus(), 300);
  };

  return (
    <div id="top">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main">
        <section className="hero wrap" aria-labelledby="hero-title">
          <div className="hero-copy">
            <h1 id="hero-title">
              Every letter should <span className="hl">render</span> right<span className="dot">.</span>
            </h1>
            <p className="lede">
              Your site may look fine in English. AksharaCheck opens it in Chromium, finds the <span lang="hi">हिंदी</span> and{' '}
              <span lang="kn">ಕನ್ನಡ</span> text that comes out broken, and asks BharatCode to explain it and draft a fix. A fix counts only when the
              browser agrees.
            </p>
            {PAGES_PREVIEW ? (
              <div className="hero-actions">
                <a className="btn primary" href={scans.length ? '#recorded' : '#reports'}>
                  {scans.length ? 'See real reports' : 'See what a report shows'}
                </a>
                <a className="btn secondary" href="#run">
                  Run it on your site
                </a>
              </div>
            ) : (
              <ScanForm onStart={start} busy={busy} aiAvailable={aiAvailable} online={online} />
            )}
            <ul className="hero-facts">
              <li>Real Chromium at phone and desktop widths</li>
              <li>Explanations in English, Hindi and Kannada</li>
              <li>Source available on GitHub</li>
            </ul>
          </div>
          <RepairDemo />
        </section>

        {resultsShown && <LiveResults busy={busy} job={job} report={report} error={error} scanId={scanId} onReset={reset} />}

        <section className="reports" id="reports" aria-labelledby="reports-title">
          <div className="wrap">
            <div className="section-head">
              <h2 id="reports-title">Every finding comes with its evidence</h2>
              <p>A report names the problem, shows how Chromium drew it, lists the exact characters, and keeps every repair BharatCode tried.</p>
            </div>
            <div className="anatomy">
              <article className="finding error example" aria-label="Example finding">
                <div className="finding-main">
                  <p className="finding-top">
                    <span className="sev error">Fix</span>
                    <strong>Broken letters</strong>
                    <span className="muted">phone and desktop</span>
                  </p>
                  <p className="finding-sample" lang="hi">
                    सूचना: परीक्षा <span className="wavy">ह िंदी</span> माध्यम में होगी
                  </p>
                  <ul className="sequences">
                    <li>
                      <span className="glyph" lang="hi">
                        ह ि
                      </span>
                      <code>U+0939 U+0020 U+093F</code>
                    </li>
                  </ul>
                  <div className="ai">
                    <p className="ai-label">What BharatCode says</p>
                    <p>The vowel sign ि was typed after a space, so it has no consonant to sit on. Remove the space in the page text.</p>
                    <p className="translation">
                      <span className="lang-name" lang="hi">
                        हिंदी
                      </span>
                      <span lang="hi">मात्रा एक खाली जगह के बाद टाइप हुई है, इसलिए वह बिंदीदार गोले पर दिखती है।</span>
                    </p>
                    <p className="translation">
                      <span className="lang-name" lang="kn">
                        ಕನ್ನಡ
                      </span>
                      <span lang="kn">ಸ್ವರ ಚಿಹ್ನೆಯನ್ನು ಖಾಲಿ ಜಾಗದ ನಂತರ ಟೈಪ್ ಮಾಡಲಾಗಿದೆ.</span>
                    </p>
                  </div>
                  <div className="repair todo">
                    <p className="repair-title">What to change</p>
                    <p>This is a typing mistake, so CSS cannot repair it. Correct the text itself.</p>
                  </div>
                </div>
              </article>
              <div className="anatomy-notes">
                <div>
                  <h3>The exact characters</h3>
                  <p>Unicode code points, so the mistake can be found with a search in your CMS or code.</p>
                </div>
                <div>
                  <h3>In the reader's language</h3>
                  <p>BharatCode explains each finding in English, Hindi and Kannada, so content editors can act on it too.</p>
                </div>
                <div>
                  <h3>CSS only where CSS helps</h3>
                  <p>Layout and font problems get a CSS repair. A typing mistake is reported as a typing mistake.</p>
                </div>
              </div>
            </div>
            {/* First how a finding reads, then the real reports that prove it. */}
            <RecordedScans scans={scans} />
          </div>
        </section>

        <section className="how wrap" id="how" aria-labelledby="how-title">
          <div className="section-head">
            <h2 id="how-title">The model suggests. The browser decides.</h2>
            <p>Findings always come from Chromium. BharatCode explains them and drafts repairs, and every repair is tested in a fresh browser before it is called a fix.</p>
          </div>
          <div className="flow" role="list">
            <div className="flow-node" role="listitem">
              <p className="flow-who">Chromium</p>
              <h3>Measures the page</h3>
              <p>Opens the page at 390 and 1440 px, reads which font drew each letter, and checks letter sequences, clipping and language tags.</p>
            </div>
            <div className="flow-arrow" aria-hidden="true">
              <svg viewBox="0 0 48 24">
                <path d="M2 12h40m-8-8 8 8-8 8" />
              </svg>
            </div>
            <div className="flow-node ai-node" role="listitem">
              <p className="flow-who">BharatCode</p>
              <h3>Explains and drafts a fix</h3>
              <p>
                <code>qwen-3.8-27b</code> explains the finding in three languages and proposes a whitelisted CSS or <code>lang</code> change.
              </p>
            </div>
            <div className="flow-arrow" aria-hidden="true">
              <svg viewBox="0 0 48 24">
                <path d="M2 12h40m-8-8 8 8-8 8" />
              </svg>
            </div>
            <div className="flow-node" role="listitem">
              <p className="flow-who">Fresh Chromium</p>
              <h3>Tests the repair</h3>
              <p>Applies it, runs every check again and confirms the text is still visible, full size and on screen.</p>
            </div>
            <div className="flow-loop" aria-hidden="true">
              <svg viewBox="0 0 100 24" preserveAspectRatio="none">
                <path d="M98 2v10H2V2" />
              </svg>
              <span>Rejected? The browser's reason goes back to BharatCode, up to three tries.</span>
            </div>
          </div>
          <ul className="guards">
            <li>
              <strong>Page text is untrusted.</strong> It is sent to the model as data, never as instructions.
            </li>
            <li>
              <strong>Only safe CSS.</strong> The model can only use a short list of layout properties. No URLs, scripts or selectors.
            </li>
            <li>
              <strong>No cheating fixes.</strong> Hiding, shrinking or moving the text off screen is rejected.
            </li>
          </ul>
        </section>

        <TextChecker />

        <section className="checks wrap" id="checks" aria-labelledby="checks-title">
          <div className="section-head">
            <h2 id="checks-title">What it checks</h2>
            <p>Four problems that make Hindi and Kannada pages hard to read, each measured in Chromium at phone and desktop widths.</p>
          </div>
          <div className="checks-grid">
            <article className="check-card">
              <div className="specimen" lang="hi">
                <span className="wavy">ह िंदी</span>
              </div>
              <h3>Broken letters</h3>
              <p>A vowel sign, virama or nukta with nothing to attach to. Browsers draw it on a dotted circle.</p>
            </article>
            <article className="check-card">
              <div className="specimen" role="img" aria-label="A Kannada word drawn as empty boxes">
                <span className="tofu" />
                <span className="tofu" />
                <span className="tofu" />
                <span className="tofu" />
              </div>
              <h3>Missing fonts</h3>
              <p>Chromium reports which font drew each letter, so a silent fallback or an empty box is caught.</p>
            </article>
            <article className="check-card">
              <div className="specimen" lang="kn">
                <span className="cut">ಪರೀಕ್ಷೆ</span>
              </div>
              <h3>Cut-off letters</h3>
              <p>A tight line height or hidden overflow cuts the parts of a letter above or below the line.</p>
            </article>
            <article className="check-card">
              <div className="specimen code">
                <code>
                  &lt;html lang=<span className="wavy">"en"</span>&gt;
                </code>
              </div>
              <h3>Wrong language tag</h3>
              <p>Hindi marked as English is read aloud in an English voice and may get the wrong font.</p>
            </article>
          </div>
        </section>

        <section className="run wrap" id="run" aria-labelledby="run-title">
          <div className="run-copy">
            <h2 id="run-title">Run it on your own site</h2>
            <p>The scanner runs on your machine with Python and Chromium. Set your BharatCode key on the server side, never in a browser.</p>
            <p className="muted">Windows, macOS and Linux. Python 3.10 or newer.</p>
            <a className="btn secondary" href={REPO + '#readme'} target="_blank" rel="noopener noreferrer">
              Full instructions on GitHub
            </a>
          </div>
          <div className="terminal">
            <div className="terminal-bar">
              <span>Windows Command Prompt</span>
              <CopyButton text={COMMANDS.join('\n')} />
            </div>
            <pre aria-label="Commands to run AksharaCheck">
              {COMMANDS.map((line) => (
                <span key={line} className="cmd">
                  <span className="prompt" aria-hidden="true">
                    &gt;
                  </span>
                  {line}
                  {'\n'}
                </span>
              ))}
            </pre>
          </div>
        </section>

        <section className="faq wrap" id="faq" aria-labelledby="faq-title">
          <h2 id="faq-title">Questions</h2>
          <div className="faq-list">
            <details>
              <summary>Does AksharaCheck change my website?</summary>
              <p>No. It only reads a public page. Repairs are tested on a copy of the page in a separate browser, never on your site.</p>
            </details>
            <details>
              <summary>Where does BharatCode come in?</summary>
              <p>
                Every finding comes from the browser. BharatCode's <code>qwen-3.8-27b</code> then explains it in English, Hindi and Kannada and drafts a
                repair. Chromium tests that repair; if it fails, the reason goes back to the model for another try.
              </p>
            </details>
            <details>
              <summary>Which languages does it support?</summary>
              <p>Hindi and Kannada. The letter rules also cover other languages in the Devanagari and Kannada scripts, such as Marathi, Nepali, Sanskrit and Tulu.</p>
            </details>
            <details>
              <summary>Can it check pages behind a login?</summary>
              <p>Not yet. It checks public pages only, and it will not open local or private network addresses.</p>
            </details>
            <details>
              <summary>Is the source code available?</summary>
              <p>
                Yes, the scanner, the rules and this site are on{' '}
                <a href={REPO} target="_blank" rel="noopener noreferrer">
                  GitHub
                </a>
                .
              </p>
            </details>
          </div>
        </section>

        <section className="cta wrap" aria-labelledby="cta-title">
          <Logo size={48} onDark />
          <h2 id="cta-title">Find the broken letters before your readers do.</h2>
          <a className="btn on-dark" href={PAGES_PREVIEW ? (scans.length ? '#recorded' : '#reports') : '#top'}>
            {PAGES_PREVIEW ? 'See the reports' : 'Check a page'}
          </a>
        </section>
      </main>
      <footer className="footer wrap">
        <div className="footer-brand">
          <Logo size={22} />
          <strong>AksharaCheck</strong>
          <span lang="hi">अक्षर जाँच</span>
          <span lang="kn">ಅಕ್ಷರ ಪರಿಶೀಲನೆ</span>
        </div>
        <nav aria-label="Footer">
          <a href={REPO} target="_blank" rel="noopener noreferrer">
            GitHub
          </a>
          <a href="https://bharatcode.ai/hackathon" target="_blank" rel="noopener noreferrer">
            BharatCode Build League 2026
          </a>
        </nav>
      </footer>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
