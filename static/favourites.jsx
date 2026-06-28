// Favourites — saved opportunities. Removing a star drops the card from the list.
// favIds is now keyed by opp.id and holds the FULL opportunity object (so we
// can render it even when its source list — live web search or seeded — isn't
// in memory anymore).
function Favourites({ go, favIds, toggleFav }) {
  const saved = Object.values(favIds)
    .filter(v => v && typeof v === 'object')
    .sort((a, b) => (b.score || 0) - (a.score || 0));
  const n = saved.length;

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">Favourites</h1>
        <p className="lede page-lede">
          {n === 0
            ? 'Star opportunities from your matches to keep them here.'
            : `${n} saved ${n === 1 ? 'opportunity' : 'opportunities'} — review or apply when you're ready.`}
        </p>
      </header>

      {n === 0 ? (
        <div className="match-empty fav-empty">
          <div className="fav-empty-star">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round"><path d="M12 3.2l2.62 5.3 5.85.85-4.23 4.12 1 5.83L12 16.9l-5.24 2.75 1-5.83L3.53 9.35l5.85-.85L12 3.2z" /></svg>
          </div>
          <p className="body">Nothing saved yet — star opportunities from Matches to see them here.</p>
          <button className="btn btn-gold" onClick={() => go('matches')}>Go to Matches</button>
        </div>
      ) : (
        <div className="match-stack">
          {saved.map(m => (
            <MatchCard key={m.id} m={m} go={go} fav={true} onToggle={() => toggleFav(m)} />
          ))}
        </div>
      )}
    </div>
  );
}
window.Favourites = Favourites;
