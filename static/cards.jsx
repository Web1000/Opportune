// Shared opportunity card components (MatchCard, CompactCard, StarButton).
// All real opportunity data comes from the Flask backend now via window.API
// (see results.jsx); the mock OPPORTUNITIES list that used to live here has
// been emptied so fresh users don't see leftover demo content.
const OPPORTUNITIES = [];
const OPP_BY_ID = {};

function matchScoreTone(s) {
  if (s >= 80) return 'green';
  if (s >= 70) return 'gold';
  return 'neutral';
}

function sourceLabel(src) {
  if (src === 'adzuna') return 'Adzuna';
  if (src === 'scholarshipscanada') return 'ScholarshipsCanada';
  return 'Indeed';
}

// Star toggle with a brief inline confirmation ("Saved to Favourites" / "Removed").
function StarButton({ active, onToggle }) {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);

  function click(e) {
    e.stopPropagation();
    const nowActive = !active;
    onToggle();
    setToast(nowActive ? 'Saved to Favourites' : 'Removed');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setToast(null), 1700);
  }

  return (
    <div className="star-wrap">
      <button
        className={"star-btn" + (active ? ' on' : '')}
        onClick={click}
        aria-pressed={active}
        aria-label={active ? 'Remove from Favourites' : 'Save to Favourites'}
        title={active ? 'Remove from Favourites' : 'Save to Favourites'}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill={active ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round">
          <path d="M12 3.2l2.62 5.3 5.85.85-4.23 4.12 1 5.83L12 16.9l-5.24 2.75 1-5.83L3.53 9.35l5.85-.85L12 3.2z" />
        </svg>
      </button>
      {toast && <span className={"star-toast" + (active ? ' star-toast-on' : '')}>{toast}</span>}
    </div>
  );
}

function MatchCard({ m, go, fav, onToggle }) {
  const tone = matchScoreTone(m.score);
  return (
    <article className="match live-card">
      <StarButton active={fav} onToggle={onToggle} />
      <div className="match-head">
        <div className="match-headl">
          <div className="live-toprow">
            <span className="live-badge"><span className="live-dot" />Live · {sourceLabel(m.source)}</span>
          </div>
          <h3 className="serif-h match-role">{m.role}</h3>
          <p className="body match-org">{m.org} · {m.location}</p>
          <div className="live-meta">
            <span className="tag match-tag">{m.type}</span>
            {m.deadline && m.deadline.toLowerCase() !== 'not specified' && (
              <span className="live-deadline">Deadline · {m.deadline}</span>
            )}
          </div>
        </div>
        <div className={"match-score tone-" + tone}>
          <div className="match-score-num">{m.score}</div>
          <div className="match-score-of">/ 100</div>
          <div className="match-bar"><span style={{ width: m.score + '%' }} /></div>
        </div>
      </div>

      <div className="match-cols live-cols">
        <div className="mcol">
          <p className="mcol-label tone-green">Why you fit</p>
          <ul className="mlist mlist-green">{m.strengths.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
        <div className="mcol">
          <p className="mcol-label tone-gold">Check before applying</p>
          <ul className="mlist mlist-gold">{m.missing.map((x, i) => <li key={i}>{x}</li>)}</ul>
        </div>
      </div>

      <div className="match-foot live-foot">
        <a className="btn btn-ghost live-view" href={m.url} target="_blank" rel="noopener noreferrer">View posting ↗</a>
        <button className="btn btn-primary match-cta" onClick={() => go('application', { job: m })}>
          Draft application materials
        </button>
      </div>
    </article>
  );
}

// Compact card — used in Home's "Recently saved" row.
function CompactCard({ m, go, fav, onToggle }) {
  const tone = matchScoreTone(m.score);
  return (
    <article className="ccard" onClick={() => go('application', { job: m })}>
      <StarButton active={fav} onToggle={onToggle} />
      <span className="live-badge ccard-badge"><span className="live-dot" />{sourceLabel(m.source)}</span>
      <h4 className="serif-h ccard-role">{m.role}</h4>
      <p className="ccard-org">{m.org}</p>
      <div className="ccard-foot">
        <span className={"ccard-score tone-" + tone}>{m.score}<span className="ccard-score-of">/100</span></span>
        <span className="tag ccard-type">{m.type}</span>
      </div>
    </article>
  );
}

Object.assign(window, { OPPORTUNITIES, OPP_BY_ID, matchScoreTone, sourceLabel, StarButton, MatchCard, CompactCard });
