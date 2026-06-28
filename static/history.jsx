// History — application materials the user has drafted. Updated live whenever a
// draft is opened (app.jsx logs into `history`); seeded with a couple of past drafts.
function HistoryView({ go, history }) {
  const items = history || [];

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">History</h1>
        <p className="lede page-lede">Every résumé and cover letter you've drafted — reopen one to review, tweak, or download.</p>
      </header>

      {items.length === 0 ? (
        <div className="match-empty fav-empty">
          <div className="fav-empty-star">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"><path d="M3.5 12a8.5 8.5 0 108.5-8.5A8.5 8.5 0 005 7" /><path d="M5 3v4h4" /><path d="M12 7.5V12l3 2" /></svg>
          </div>
          <p className="body">Nothing drafted yet — draft application materials from a match to see them here.</p>
          <button className="btn btn-gold" onClick={() => go('matches')}>Go to Matches</button>
        </div>
      ) : (
        <div className="hist-list">
          {items.map((h, i) => (
            <article key={h.id + '-' + i} className="hist-row" onClick={() => go('application', { job: h })}>
              <div className="hist-main">
                <div className="hist-toprow">
                  <span className="live-badge"><span className="live-dot" />{h.source === 'indeed' ? 'Indeed' : 'ScholarshipsCanada'}</span>
                  <span className="hist-date">{h.date}</span>
                </div>
                <h3 className="serif-h hist-role">{h.role}</h3>
                <p className="hist-org">{h.org}</p>
                <p className="hist-kind">Résumé + cover letter</p>
              </div>
              <div className="hist-actions">
                <span className="btn-text hist-open">Open →</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
window.HistoryView = HistoryView;
