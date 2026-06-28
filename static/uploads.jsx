// My resumes — the library of résumés the user has uploaded. Several can be kept
// on file, and the user can SELECT MULTIPLE at once: the selected résumés are
// combined into one profile so the AI sees everything across them (e.g. work
// history on one résumé, projects on another). The combined profile is what
// matching and tailored generation draw from. Uploading accepts multiple PDFs.
//
// Distinct from "My applications" (the tailored résumé + cover letter outputs);
// this tab is the source résumés you generate FROM.

function fmtUploadedDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (isNaN(d)) return '';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function ResumeFileGlyph() {
  return (
    <span className="mres-glyph">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        <path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M9.5 12h6M9.5 15.5h6" />
      </svg>
    </span>
  );
}

function ResumeCheck({ on }) {
  return (
    <span className={"mres-check" + (on ? ' on' : '')} aria-hidden="true">
      {on && (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 12.5l4.5 4.5L19 7" />
        </svg>
      )}
    </span>
  );
}

function MyResumes({ go, currentUser, demo, selectedIds, onApply }) {
  const userId = currentUser && currentUser.user_id;
  const ids = selectedIds || [];
  const selectedSet = new Set(ids.map(String));
  const [resumes, setResumes] = useState([]);
  const [loading, setLoading] = useState(!!userId);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef(null);

  async function refresh() {
    if (!userId) return;
    const rs = await window.API.listResumes(userId);
    setResumes(rs);
  }

  // Load this user's uploaded résumés on mount (and whenever the user changes).
  useEffect(() => {
    if (!userId) { setLoading(false); return; }
    let cancelled = false;
    setLoading(true);
    setError('');
    window.API.listResumes(userId)
      .then(rs => { if (!cancelled) setResumes(rs); })
      .catch(e => { if (!cancelled) setError(e.message || 'Could not load your résumés.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [userId]);

  function openPicker() {
    if (fileRef.current) fileRef.current.click();
  }

  // Add/remove a résumé from the combined-profile selection.
  function toggle(id) {
    if (!onApply) return;
    const key = String(id);
    const next = selectedSet.has(key)
      ? ids.filter(x => String(x) !== key)
      : [...ids, id];
    onApply(next);
  }

  // Upload one or more PDFs. Each becomes its own saved résumé and is added to
  // the selection so the newly uploaded info is included right away.
  async function onFiles(e) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setUploading(true);
    setError('');
    const newIds = [];
    for (const f of files) {
      try {
        const data = await window.API.uploadResume(f, userId, demo);
        if (data && data.profile_id) newIds.push(data.profile_id);
      } catch (err) {
        setError(err.message || `Couldn't upload ${f.name}.`);
      }
    }
    try { await refresh(); } catch (_) { /* list refresh is best-effort */ }
    setUploading(false);
    e.target.value = ''; // allow re-uploading the same file
    if (newIds.length && onApply) onApply([...ids, ...newIds]);
  }

  async function remove(id) {
    const prev = resumes;
    setResumes(rs => rs.filter(r => r.profile_id !== id)); // optimistic
    if (selectedSet.has(String(id)) && onApply) {
      onApply(ids.filter(x => String(x) !== String(id))); // drop from the combined profile
    }
    try {
      await window.API.deleteResume(id);
    } catch (e) {
      setResumes(prev); // restore on failure
      setError(e.message || 'Could not delete that résumé.');
    }
  }

  const usingCount = ids.length;

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">My resumes</h1>
        <p className="lede page-lede">Keep several résumés on file and select the ones to use — the AI combines every selected résumé, so info spread across them is all available when matching and drafting.</p>
      </header>

      {error && <p className="body autosave-err" style={{ marginBottom: 16 }}>{error}</p>}
      <input ref={fileRef} type="file" accept="application/pdf" multiple onChange={onFiles} style={{ display: 'none' }} />

      {!userId ? (
        <div className="match-empty fav-empty">
          <p className="body">Sign in to upload and save your résumés.</p>
          <button className="btn btn-gold" onClick={() => go('auth')}>Sign in</button>
        </div>
      ) : loading ? (
        <div className="match-empty fav-empty">
          <p className="body">Loading your résumés…</p>
        </div>
      ) : (
        <React.Fragment>
          <div className="parse-row">
            <p className="body parse-copy">{resumes.length} {resumes.length === 1 ? 'résumé' : 'résumés'} on file</p>
            <button className="btn btn-gold parse-btn" onClick={openPicker} disabled={uploading}>
              {uploading ? 'Uploading…' : 'Upload résumé'}
            </button>
          </div>

          {resumes.length > 0 && (
            <p className="cap mres-using-note">
              {usingCount === 0
                ? 'None selected — pick one or more to match and draft from.'
                : usingCount === 1
                  ? 'Using 1 résumé for matches & drafts.'
                  : `Combining ${usingCount} résumés into one profile for matches & drafts.`}
            </p>
          )}

          {resumes.length === 0 ? (
            <div className="match-empty fav-empty">
              <p className="body">No résumés yet — upload one (or several) to match and draft from.</p>
              <button className="btn btn-gold" onClick={openPicker} disabled={uploading}>
                {uploading ? 'Uploading…' : 'Upload résumé'}
              </button>
            </div>
          ) : (
            <div className="mres-list">
              {resumes.map(r => {
                const selected = selectedSet.has(String(r.profile_id));
                return (
                  <article
                    key={r.profile_id}
                    className={"mres-row mres-row-click" + (selected ? ' mres-row-primary' : '')}
                    role="checkbox"
                    aria-checked={selected}
                    onClick={() => toggle(r.profile_id)}
                  >
                    <ResumeCheck on={selected} />
                    <ResumeFileGlyph />
                    <div className="mres-info">
                      <div className="mres-namerow">
                        <h3 className="serif-h mres-name">{r.name}</h3>
                        {selected && <span className="mres-pill">In use</span>}
                      </div>
                      <p className="mres-meta">{r.filename}{r.created_at ? ` · Uploaded ${fmtUploadedDate(r.created_at)}` : ''}</p>
                    </div>
                    <div className="mres-actions">
                      <button className="btn-text mres-action mres-del" onClick={(e) => { e.stopPropagation(); remove(r.profile_id); }}>Delete</button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </React.Fragment>
      )}
    </div>
  );
}
window.MyResumes = MyResumes;
