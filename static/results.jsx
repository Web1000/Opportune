// Matches — search-driven. Pulls real matches from the Flask backend:
//   POST /match-opportunities         -> seeded scholarships + internships, scored
//   POST /search-live-opportunities   -> live Indeed + ScholarshipsCanada hits, scored
//
// `matchData` is lifted to App so switching to Favourites / History / Account
// and back here does NOT re-run the (slow) search. A search runs ONLY when the
// user presses the Search button here, or right after clicking "Find my matches"
// on the form (which sets matchData.pendingSearch). Entering the tab never
// auto-searches.
function Results({ go, favIds, toggleFav, profile, demo, demoReady, matchData, setMatchData }) {
  const [source, setSource] = useState('jobs');
  const [company, setCompany] = useState('');
  const [employment, setEmployment] = useState('Any');
  const [err, setErr] = useState('');

  const { seedResults, liveResults, seedLoading, liveLoading, hasMatched, liveNotice, pendingSearch } = matchData;

  // Combine + filter for the source pill the user picked.
  function visible() {
    const all = [...seedResults, ...liveResults];
    return all.filter(m => {
      const isScholarship = (m.type || '').toLowerCase().includes('scholar');
      if (source === 'scholarships' && !isScholarship && m.source !== 'scholarshipscanada') return false;
      if (source === 'jobs' && isScholarship) return false;
      return true;
    }).sort((a, b) => b.score - a.score);
  }

  async function runSeed() {
    setMatchData(prev => ({ ...prev, seedLoading: true }));
    try {
      const data = await window.API.matchOpportunities(profile, demo);
      setMatchData(prev => ({ ...prev, seedResults: data, seedLoading: false }));
    } catch (e) {
      console.warn('match-opportunities failed:', e);
      setMatchData(prev => ({ ...prev, seedLoading: false }));
    }
  }

  async function runLive(opts = {}) {
    setMatchData(prev => ({ ...prev, liveLoading: true }));
    try {
      const { results, notice } = await window.API.searchLiveOpportunities(profile, { mock: demo, ...opts });
      setMatchData(prev => ({ ...prev, liveResults: results, liveNotice: notice, liveLoading: false }));
    } catch (e) {
      console.warn('search-live-opportunities failed:', e);
      setMatchData(prev => ({ ...prev, liveLoading: false }));
    }
  }

  // We do NOT search on entering the tab. The page searches on its own only
  // right after the user clicks "Find my matches" on the form, which sets
  // `pendingSearch`; we honor that once (when the profile + demo mode are known)
  // then clear it. Every other arrival just shows the prompt or cached results.
  useEffect(() => {
    if (!pendingSearch) return;
    if (!demoReady) return;
    if (!profile) {
      setErr('No profile loaded — fill in Your info first.');
      return;
    }
    setErr('');
    setMatchData(prev => ({ ...prev, hasMatched: true, pendingSearch: false }));
    if (demo && !seedResults.length) runSeed(); // seeded sample list, demo only
    runLive();
  }, [pendingSearch, demoReady, profile]);

  // The search button — the only thing that searches on a normal visit.
  function runSearch(e) {
    if (e) e.preventDefault();
    if (!profile) { setErr('No profile loaded — fill in Your info first.'); return; }
    setErr('');
    setMatchData(prev => ({ ...prev, hasMatched: true, pendingSearch: false }));
    const filters = {};
    if (company.trim()) filters.company = company.trim();
    if (source === 'jobs' && employment !== 'Any') filters.employment_type = employment;
    const sources = source === 'jobs' ? ['indeed'] : ['scholarshipscanada'];
    if (demo && !seedResults.length) runSeed(); // seeded sample list, demo only
    runLive({ sources, filters });
  }

  const srcLabel = source === 'jobs' ? 'job boards' : 'ScholarshipsCanada';
  const results = visible();
  // Show the full-page spinner only while we have nothing to display yet and a
  // search is still running — works whether or not the seeded list is included.
  const anyData = seedResults.length > 0 || liveResults.length > 0;
  const stillLoading = (seedLoading || liveLoading) && !anyData;

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">Your matches</h1>
        <p className="lede page-lede">Set your filters and search Indeed and ScholarshipsCanada — matches come back ranked by fit with your profile.</p>
      </header>

      <form className="live-panel" onSubmit={runSearch}>
        <div className="live-srcrow">
          <div className="seg live-seg">
            <button type="button" className={"seg-btn" + (source === 'jobs' ? ' on' : '')} onClick={() => setSource('jobs')}>Jobs &amp; internships</button>
            <button type="button" className={"seg-btn" + (source === 'scholarships' ? ' on' : '')} onClick={() => setSource('scholarships')}>Scholarships</button>
          </div>
          <p className="cap live-src-note">{source === 'jobs' ? 'Searching Indeed, LinkedIn, Job Bank & company sites' : 'Searching scholarshipscanada.com'}</p>
        </div>

        <div className="live-filters">
          <div className="field live-field">
            <label className="field-label">Company / organization <span className="live-opt">optional</span></label>
            <input className="input" placeholder={source === 'jobs' ? 'e.g. Shopify, Google' : 'e.g. TD, a foundation'} value={company} onChange={e => setCompany(e.target.value)} />
          </div>
          {source === 'jobs' && (
            <div className="field live-field live-field-emp">
              <label className="field-label">Employment type</label>
              <div className="seg live-seg-emp">
                {['Any', 'Full-time', 'Part-time'].map(opt => (
                  <button type="button" key={opt} className={"seg-btn" + (employment === opt ? ' on' : '')} onClick={() => setEmployment(opt)}>{opt}</button>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="live-actions">
          <button type="submit" className="btn btn-gold live-search-btn" disabled={liveLoading}>
            {liveLoading ? 'Searching…' : (hasMatched ? 'Update matches' : 'Search')}
          </button>
        </div>
      </form>

      {err && (
        <div className="match-empty">
          <p className="body">{err}</p>
          <button className="btn btn-gold" onClick={() => go('form')}>Go to Your info</button>
        </div>
      )}

      {stillLoading && !err && (
        <div className="live-loading">
          <div className="loading-mark"><span className="loading-pulse" /></div>
          <p className="body" style={{ marginTop: 16 }}>
            {demo ? 'Loading sample matches…' : `Searching ${srcLabel} and scoring matches…`}
          </p>
          <p className="cap" style={{ marginTop: 8 }}>
            {demo ? 'Demo mode — no API calls.' : 'This usually takes 20–40 seconds for live mode.'}
          </p>
        </div>
      )}

      {!stillLoading && !err && !hasMatched && (
        <div className="match-empty">
          <p className="body">Set your filters above and press Search to find matches.</p>
        </div>
      )}

      {!stillLoading && !err && hasMatched && (
        <React.Fragment>
          <div className="results-sub">
            <h2 className="serif-h results-h">{results.length} {results.length === 1 ? 'match' : 'matches'}</h2>
            <p className="cap">
              {liveLoading
                ? (demo ? 'Seeded results below — live web results still loading…' : 'Searching live opportunities…')
                : `From your ${source === 'jobs' ? 'job' : 'scholarship'} search · scored against your profile`}
            </p>
          </div>
          {liveNotice && liveNotice.type === 'company_not_found' && (
            <div className="live-notice">
              <p className="live-notice-title">No jobs found at <strong>{liveNotice.company}</strong>.</p>
              <p className="live-notice-sub">
                {results.length
                  ? 'Here are similar positions matched to your profile:'
                  : 'Try a different company, or widen the employment type.'}
              </p>
            </div>
          )}
          {results.length === 0 ? (
            !liveNotice ? (
              <div className="match-empty">
                <p className="body">No matches yet for that filter. Try a different company or widen the type.</p>
              </div>
            ) : null
          ) : (
            <div className="match-stack">
              {results.map(m => (
                <MatchCard key={m.id} m={m} go={go} fav={!!favIds[m.id]} onToggle={() => toggleFav(m)} />
              ))}
            </div>
          )}
        </React.Fragment>
      )}
    </div>
  );
}
window.Results = Results;
