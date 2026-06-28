// My applications — the tailored applications the user has drafted and saved,
// organized by match. Each card is one opportunity; clicking it opens the saved
// résumé + cover letter (most recent edits) in the editor. Fresh users have
// none yet; the empty state nudges them to draft one from a match. Guests have
// nowhere to persist, so they get a prompt to sign in.

// Turn an ISO timestamp into a short, human "Jun 13, 2026" label.
function formatStamp(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function FileGlyph() {
  return (
    <span className="mres-glyph">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M9.5 12h6M9.5 15.5h6" />
      </svg>
    </span>
  );
}

function MyApplications({ go, currentUser }) {
  const userId = currentUser && currentUser.user_id;
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(!!userId);
  const [error, setError] = useState('');

  // Load this user's saved applications on mount (and whenever the signed-in
  // user changes). Guests have no user_id, so there's nothing to fetch.
  useEffect(() => {
    if (!userId) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setError('');
    window.API.listApplications(userId)
      .then(rs => { if (!cancelled) setApps(rs); })
      .catch(e => { if (!cancelled) setError(e.message || 'Could not load your applications.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [userId]);

  async function remove(id) {
    const prev = apps;
    setApps(rs => rs.filter(a => a.id !== id)); // optimistic
    try {
      await window.API.deleteApplication(id);
    } catch (e) {
      setApps(prev); // restore on failure
      setError(e.message || 'Could not delete that application.');
    }
  }

  function savedParts(a) {
    const parts = [];
    if (a.has_resume) parts.push('Résumé');
    if (a.has_cover) parts.push('Cover letter');
    return parts.length ? parts.join(' + ') : 'Empty';
  }

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">My applications</h1>
        <p className="lede page-lede">Every match you've drafted for, organized in one place. Open one to keep editing its résumé and cover letter.</p>
      </header>

      {error && <p className="body autosave-err" style={{ marginBottom: 16 }}>{error}</p>}

      {!userId ? (
        <div className="match-empty fav-empty">
          <p className="body">Sign in to save and revisit your applications.</p>
          <button className="btn btn-gold" onClick={() => go('auth')}>Sign in</button>
        </div>
      ) : loading ? (
        <div className="match-empty fav-empty">
          <p className="body">Loading your applications…</p>
        </div>
      ) : (
        <React.Fragment>
          <div className="parse-row">
            <p className="body parse-copy">{apps.length} {apps.length === 1 ? 'application' : 'applications'} on file</p>
            <button className="btn btn-gold parse-btn" onClick={() => go('matches')}>Find matches</button>
          </div>

          {apps.length === 0 ? (
            <div className="match-empty fav-empty">
              <p className="body">No applications yet — draft one from a match to save it here.</p>
              <button className="btn btn-gold" onClick={() => go('matches')}>Go to matches</button>
            </div>
          ) : (
            <div className="mres-list">
              {apps.map(a => (
                <article key={a.id} className="mres-row mres-row-click" onClick={() => go('appdetail', { appId: a.id })}>
                  <FileGlyph />
                  <div className="mres-info">
                    <div className="mres-namerow">
                      <h3 className="serif-h mres-name">{a.name}</h3>
                    </div>
                    <p className="mres-meta">
                      {savedParts(a)}{a.updated_at ? ` · Updated ${formatStamp(a.updated_at)}` : ''}
                    </p>
                  </div>
                  <div className="mres-actions">
                    <button className="btn-text mres-action" onClick={(e) => { e.stopPropagation(); go('appdetail', { appId: a.id }); }}>Open</button>
                    <button className="btn-text mres-action mres-del" onClick={(e) => { e.stopPropagation(); remove(a.id); }}>Delete</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </React.Fragment>
      )}
    </div>
  );
}
window.MyApplications = MyApplications;
