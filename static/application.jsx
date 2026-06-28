// Application editor — tailored résumé + cover letter for one match.
//
// Two modes:
//   • Draft mode (from a match): generates fresh materials on mount.
//   • Saved mode (from "My applications", via appId): loads the saved
//     application and lets the user keep editing it.
// Either way the résumé and cover letter are edited independently and saved
// with their own buttons; saving upserts the one row for this match (keyed by
// matchKey), so re-saving updates rather than duplicating. Download PDF posts
// the structured resume_data to /render-resume-pdf.
//
// Small inline markdown renderer (`mdToHtml`) keeps the doc preview readable
// without pulling in a library — headings, bullets, **bold**, _italic_, links.
function mdToHtml(md) {
  if (!md) return '';
  const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const inline = s => esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/_([^_]+)_/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  const lines = md.split('\n');
  let html = '', inList = false;
  for (const raw of lines) {
    const line = raw.replace(/\r$/, '');
    if (/^\s*[-*]\s+/.test(line)) { if (!inList) { html += '<ul>'; inList = true; } html += '<li>' + inline(line.replace(/^\s*[-*]\s+/, '')) + '</li>'; continue; }
    if (inList) { html += '</ul>'; inList = false; }
    if (/^###\s+/.test(line)) html += '<h4>' + inline(line.replace(/^###\s+/, '')) + '</h4>';
    else if (/^##\s+/.test(line)) html += '<h3>' + inline(line.replace(/^##\s+/, '')) + '</h3>';
    else if (/^#\s+/.test(line)) html += '<h2>' + inline(line.replace(/^#\s+/, '')) + '</h2>';
    else if (line.trim() !== '') html += '<p>' + inline(line) + '</p>';
  }
  if (inList) html += '</ul>';
  return html;
}

// ── Draft cache ────────────────────────────────────────────────────────────
// Draft generations are cached by match key at the MODULE level (not in
// component state), so an in-flight generation survives tab switches. Leaving
// the page unmounts <Application>, but the request keeps running here — so when
// the user returns to the match, the draft is still loading (or already done)
// instead of restarting from scratch.
const _draftCache = (window.__draftCache = window.__draftCache || {});

function _startDraft(key, run) {
  let e = _draftCache[key];
  if (e && (e.status === 'loading' || e.status === 'done')) return e; // reuse in-flight / finished
  e = { status: 'loading', result: null, error: null };
  e.promise = Promise.resolve().then(run)
    .then(r => { e.status = 'done'; e.result = r; return r; })
    .catch(err => { e.status = 'error'; e.error = err; throw err; });
  _draftCache[key] = e;
  return e;
}

function Application({ go, job, profile, demo, currentUser, showToast, appId }) {
  const savedMode = appId != null;
  const userId = currentUser && currentUser.user_id;
  const j = job || { role: 'Software Engineering Intern', org: 'Shopify' };

  const [loading, setLoading] = useState(true);   // generating (draft) or fetching (saved)
  const [err, setErr] = useState('');
  const [ready, setReady] = useState(false);

  // Structured résumé (drives the PDF) + the editable text copies.
  const [resumeData, setResumeData] = useState(null);
  const [resumeText, setResumeText] = useState('');
  const [coverText, setCoverText] = useState('');
  // `baseline` is the last-saved (or as-loaded) text for each document — the
  // diff against it is what's unsaved. Tracked per-document so the two save
  // buttons clear only their own half.
  const [baseline, setBaseline] = useState({ resume: '', cover: '' });
  const [extras, setExtras] = useState({ missing: [], suggestions: [] }); // draft only

  // Identity of the match this application belongs to. matchKey makes saving an
  // upsert (one row per match); opportunityName is its label in My applications.
  const [matchKey, setMatchKey] = useState('');
  const [opportunityName, setOpportunityName] = useState('');

  const [editResume, setEditResume] = useState(false);
  const [editCover, setEditCover] = useState(false);
  const [savingResume, setSavingResume] = useState(false);
  const [savingCover, setSavingCover] = useState(false);
  const [saveErr, setSaveErr] = useState('');
  const [downloading, setDownloading] = useState(false);

  // True while THIS component instance is mounted — lets an awaited generation
  // that finishes after the user navigated away skip its setState (the result
  // is safe in the module cache and is applied when they return).
  const mountedRef = useRef(true);
  useEffect(() => () => { mountedRef.current = false; }, []);

  const resumeDirty = ready && resumeText !== baseline.resume;
  const coverDirty = ready && coverText !== baseline.cover;
  // The PDF now renders from the edited résumé markdown, so it can be downloaded
  // whenever there's résumé text — even before the structured data is saved.
  const canDownload = !!(resumeText && resumeText.trim());

  // A stable per-opportunity key: prefer the posting URL, then its id, then a
  // role|org fallback. Must match across draft + saved so re-saving upserts.
  function deriveMatchKey(jb) {
    if (jb && jb.url && jb.url !== '#') return jb.url;
    if (jb && jb.id != null) return String(jb.id);
    return `${(jb && jb.role) || ''}|${(jb && jb.org) || ''}`;
  }

  // Convert the live frontend match shape back to the backend opportunity dict
  // that /generate-application expects.
  function buildBackendOpportunity() {
    if (j._raw_opp) return j._raw_opp;
    return {
      id: j.id, title: j.role, organization: j.org, type: j.type,
      field: '', location: j.location, gpa_requirement: '',
      required_skills: '', description: '', deadline: j.deadline,
      url: j.url, source: j.source,
    };
  }

  // Populate component state from a finished generation result.
  function applyDraftResult(result) {
    const r = result.tailored_resume || '';
    const c = result.cover_letter || '';
    setResumeData(result.resume_data || {});
    setResumeText(r); setCoverText(c);
    setBaseline({ resume: r, cover: c });
    setExtras({
      missing: result.missing_details_needed || [],
      suggestions: result.resume_improvement_suggestions || [],
    });
    setMatchKey(deriveMatchKey(j));
    setOpportunityName(j.org ? `${j.role} — ${j.org}` : (j.role || 'Tailored résumé'));
    setEditResume(false); setEditCover(false);
    setReady(true);
  }

  // Draft generation. Runs through the module-level cache so it keeps going when
  // the user switches tabs; `force` (Regenerate) discards any cached draft first.
  async function runGenerate(force) {
    setErr(''); setSaveErr('');
    const key = deriveMatchKey(j);
    if (force) delete _draftCache[key];
    const entry = _startDraft(key, () =>
      window.API.generateApplication(profile, buildBackendOpportunity(), demo));
    if (entry.status === 'done') { applyDraftResult(entry.result); setLoading(false); return; }
    if (entry.status === 'error') {
      setErr((entry.error && entry.error.message) || 'Generation failed.'); setLoading(false); return;
    }
    setLoading(true); setReady(false);
    try {
      const result = await entry.promise;
      if (!mountedRef.current) return;       // navigated away — the cache holds the result
      applyDraftResult(result);
    } catch (e) {
      if (mountedRef.current) setErr(e.message || 'Generation failed.');
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }

  async function loadSaved() {
    setLoading(true); setErr(''); setSaveErr(''); setReady(false);
    try {
      const a = await window.API.getApplication(appId);
      const r = a.tailored_resume || '';
      const c = a.cover_letter || '';
      setResumeData(a.resume_data || {});
      setResumeText(r); setCoverText(c);
      setBaseline({ resume: r, cover: c });
      setExtras({ missing: [], suggestions: [] });
      setMatchKey(a.match_key || String(appId));
      setOpportunityName(a.opportunity_name || 'Saved application');
      setEditResume(false); setEditCover(false);
      setReady(true);
    } catch (e) {
      setErr(e.message || 'Could not load this application.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (savedMode) { loadSaved(); return; }
    if (!profile) { setErr('No profile — fill in Your info first.'); setLoading(false); return; }
    runGenerate();
  }, []);

  async function saveResume() {
    if (!userId) { go('auth', { mode: 'signin' }); return; }
    setSavingResume(true); setSaveErr('');
    try {
      await window.API.saveApplication({
        userId, matchKey, opportunityName,
        resumeData: resumeData || {}, tailoredResume: resumeText,
      });
      setBaseline(b => ({ ...b, resume: resumeText })); // clears the résumé dirty flag
      if (showToast) showToast('Résumé saved to My applications');
    } catch (e) {
      setSaveErr(e.message || 'Could not save résumé.');
    } finally {
      setSavingResume(false);
    }
  }

  async function saveCover() {
    if (!userId) { go('auth', { mode: 'signin' }); return; }
    setSavingCover(true); setSaveErr('');
    try {
      await window.API.saveApplication({
        userId, matchKey, opportunityName, coverLetter: coverText,
      });
      setBaseline(b => ({ ...b, cover: coverText })); // clears the cover-letter dirty flag
      if (showToast) showToast('Cover letter saved to My applications');
    } catch (e) {
      setSaveErr(e.message || 'Could not save cover letter.');
    } finally {
      setSavingCover(false);
    }
  }

  async function downloadPdf() {
    if (!canDownload) return;
    setDownloading(true);
    try {
      const blob = await window.API.renderResumePdf(resumeData, resumeText);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const slug = (opportunityName || 'tailored').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      a.href = url;
      a.download = `resume-${slug || 'tailored'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setSaveErr('PDF download failed: ' + e.message);
    } finally {
      setDownloading(false);
    }
  }

  const dirty = resumeDirty || coverDirty;
  const backTo = savedMode ? 'resumes' : 'matches';
  const backLabel = savedMode ? 'Back to My applications' : 'Back to matches';

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">{savedMode ? 'Saved application' : 'AI Opportunity Matcher'}</h1>
        <p className="lede page-lede">
          {ready
            ? <React.Fragment>Tailored for <strong className="app-target">{opportunityName}</strong>. Edit either document, then save each on its own.</React.Fragment>
            : (savedMode ? 'Loading your saved application…' : 'Drafting your materials…')}
        </p>
      </header>

      <div className="back-row">
        <button className="btn-text back-link" onClick={() => go(backTo)}>← {backLabel}</button>
      </div>

      {loading ? (
        <div className="app-regen">
          <div className="loading-mark"><span className="loading-pulse" /></div>
          <p className="body" style={{ marginTop: 18 }}>
            {savedMode ? 'Loading your saved application…' : (demo ? 'Loading sample materials…' : 'Drafting your résumé and cover letter…')}
          </p>
          {!savedMode && (
            <p className="cap" style={{ marginTop: 8 }}>{demo ? 'Demo mode — instant.' : 'Usually 15–25 seconds.'}</p>
          )}
        </div>
      ) : err ? (
        <div className="match-empty">
          <p className="body" style={{ color: '#b14a2a' }}>{err}</p>
          <button className="btn btn-gold" onClick={() => go(backTo)}>{backLabel}</button>
        </div>
      ) : (
      <React.Fragment>
        {/* Résumé */}
        <section className="doc">
          <div className="doc-head">
            <h2 className="serif-h doc-title">Tailored résumé</h2>
            <div className="doc-tools">
              <button className="btn-text doc-toggle" onClick={() => setEditResume(v => !v)}>
                {editResume ? 'Preview' : 'Edit'}
              </button>
              <button className="btn btn-gold doc-dl" onClick={downloadPdf} disabled={downloading || !canDownload}>
                {downloading ? 'Compiling…' : 'Download PDF'}
              </button>
            </div>
          </div>
          {editResume ? (
            <textarea className="input doc-edit" value={resumeText} onChange={e => setResumeText(e.target.value)} aria-label="Edit résumé" />
          ) : (
            <div className="doc-body" dangerouslySetInnerHTML={{ __html: mdToHtml(resumeText) }} />
          )}
        </section>

        {/* Cover letter */}
        <section className="doc">
          <div className="doc-head">
            <h2 className="serif-h doc-title">Cover letter</h2>
            <button className="btn-text doc-toggle" onClick={() => setEditCover(v => !v)}>
              {editCover ? 'Preview' : 'Edit'}
            </button>
          </div>
          {editCover ? (
            <textarea className="input doc-edit doc-edit-letter" value={coverText} onChange={e => setCoverText(e.target.value)} aria-label="Edit cover letter" />
          ) : (
            <div className="doc-body letter" dangerouslySetInnerHTML={{ __html: mdToHtml(coverText) }} />
          )}
        </section>

        {/* What to strengthen — only shown for a fresh draft */}
        {(extras.missing.length > 0 || extras.suggestions.length > 0) && (
          <div className="strengthen">
            {extras.missing.length > 0 && (
              <React.Fragment>
                <p className="mcol-label tone-ink">Still needed</p>
                <ul className="mlist mlist-ink">{extras.missing.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </React.Fragment>
            )}
            {extras.suggestions.length > 0 && (
              <React.Fragment>
                <p className="mcol-label tone-ink" style={{ marginTop: 14 }}>What to strengthen</p>
                <ul className="mlist mlist-ink">{extras.suggestions.map((x, i) => <li key={i}>{x}</li>)}</ul>
              </React.Fragment>
            )}
          </div>
        )}

        {saveErr && <p className="body autosave-err save-note">{saveErr}</p>}
        <div className="app-actions">
          {!savedMode && <button className="btn btn-ghost" onClick={() => runGenerate(true)}>Regenerate</button>}
          <button className="btn btn-gold" onClick={saveResume} disabled={savingResume}>
            {savingResume ? 'Saving…' : (userId ? 'Save résumé' : 'Sign in to save')}
          </button>
          <button className="btn btn-gold" onClick={saveCover} disabled={savingCover}>
            {savingCover ? 'Saving…' : (userId ? 'Save cover letter' : 'Sign in to save')}
          </button>
        </div>
      </React.Fragment>
      )}

      {dirty && !savingResume && !savingCover && (
        <div className="draft-toast" role="status" aria-live="polite">
          <span className="draft-toast-dot" aria-hidden="true" />
          {resumeDirty && coverDirty
            ? 'Unsaved résumé and cover letter changes'
            : resumeDirty ? 'Unsaved résumé changes' : 'Unsaved cover letter changes'}
        </div>
      )}
    </div>
  );
}
window.Application = Application;
