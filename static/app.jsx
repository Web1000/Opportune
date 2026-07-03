// Root app — view state machine + shared chrome.
const { useState, useEffect, useRef } = React;

// ── Tweakable presets: three expressive levers that reshape the whole feel ──
// Accent — recolors the paper fan, buttons, and every gold accent in one move.
const ACCENTS = {
  gold:   { pale: [251, 243, 197], gold: [255, 203, 61],
    vars: { '--gold': '#B5840A', '--gold-soft': '#FFDD6B', '--gold-paper': '#FFCB3D', '--gold-pale': '#FBF1C4', '--gold-btn-1': '#FFDA63', '--gold-btn-2': '#FFC529', '--accent-glow': 'rgba(255,203,80,0.16)' } },
  citrus: { pale: [249, 247, 205], gold: [255, 221, 26],
    vars: { '--gold': '#9C8200', '--gold-soft': '#FFE85C', '--gold-paper': '#FFDD1A', '--gold-pale': '#FBF6C0', '--gold-btn-1': '#FFE658', '--gold-btn-2': '#FFD400', '--accent-glow': 'rgba(255,221,40,0.18)' } },
  ember:  { pale: [250, 228, 198], gold: [255, 138, 52],
    vars: { '--gold': '#BF560E', '--gold-soft': '#FFB377', '--gold-paper': '#FF8E3C', '--gold-pale': '#FBE4CE', '--gold-btn-1': '#FFA85C', '--gold-btn-2': '#FB7A22', '--accent-glow': 'rgba(255,140,60,0.16)' } },
  sage:   { pale: [233, 238, 201], gold: [140, 178, 74],
    vars: { '--gold': '#5C7A2C', '--gold-soft': '#B6CE7C', '--gold-paper': '#93B84B', '--gold-pale': '#E7EECC', '--gold-btn-1': '#AECC66', '--gold-btn-2': '#84AC3E', '--accent-glow': 'rgba(150,184,75,0.16)' } },
};
// Atmosphere — shifts the surfaces from airy translucent glass to grounded warm paper.
const ATMOS = {
  airy:     { '--bg-top': '#FEFEFC', '--bg-mid': '#FBFAF6', '--bg-bot': '#F6F4EE', '--bg-radial': 'rgba(255,255,255,0.97)', '--panel-bg': 'rgba(255,255,255,0.42)', '--panel-border': 'rgba(255,255,255,0.6)', '--topbar-bg': 'rgba(255,255,255,0.46)' },
  balanced: { '--bg-top': '#FDFCF9', '--bg-mid': '#F8F5EF', '--bg-bot': '#F1EDE3', '--bg-radial': 'rgba(255,255,255,0.9)', '--panel-bg': 'rgba(255,255,255,0.62)', '--panel-border': 'rgba(232,227,216,0.9)', '--topbar-bg': 'rgba(253,252,249,0.62)' },
  grounded: { '--bg-top': '#F5F1E8', '--bg-mid': '#EEE9DE', '--bg-bot': '#E5DECE', '--bg-radial': 'rgba(255,255,255,0.55)', '--panel-bg': '#FBFAF6', '--panel-border': '#E6E0D2', '--topbar-bg': 'rgba(247,244,237,0.92)' },
};
// Paper fan — restages the signature motif from a tight stack to a lavish sweep.
const FANS = {
  tight:  { count: 9,  startAngle: -4,  sweep: 122, sizeScale: 0.82 },
  spread: { count: 13, startAngle: -10, sweep: 164, sizeScale: 1 },
  lavish: { count: 20, startAngle: -16, sweep: 205, sizeScale: 1.16 },
};
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "gold",
  "atmosphere": "balanced",
  "fanStyle": "spread"
}/*EDITMODE-END*/;

function Toggle({ on, onClick }) {
  return (
    <button className={"toggle" + (on ? ' on' : '')} onClick={onClick} aria-label="Toggle demo mode">
      <span className="toggle-knob" />
    </button>
  );
}

function TopBar({ go, demo, setDemo, tab, onTab, showTabs }) {
  return (
    <div className="topbar">
      <div className="topbar-inner">
        <div className="topbar-left">
          <span className="logo logo-sm" onClick={() => go('welcome')}>Opportune</span>
          <span className="topbar-sep">·</span>
          <a className="topbar-muted-link" onClick={() => go('auth', { mode: 'signin' })}>Sign in</a>
        </div>
        {showTabs && (
          <div className="topbar-tabs">
            <button className={"ttab" + (tab === 'info' ? ' on' : '')} onClick={() => onTab('info')}>Your info</button>
            <button className={"ttab" + (tab === 'matches' ? ' on' : '')} onClick={() => onTab('matches')}>Matches</button>
          </div>
        )}
        <div className="topbar-right">
          <span className="topbar-mode">{demo ? 'Demo mode' : 'Searching LIVE results'}</span>
          <Toggle on={demo} onClick={() => setDemo(!demo)} />
        </div>
      </div>
    </div>
  );
}
window.TopBar = TopBar;

function Loading({ label = 'Finding your matches…', sub = 'Scoring opportunities against your profile — this usually takes 20–30 seconds.' }) {
  return (
    <div className="loading">
      <div className="loading-mark"><span className="loading-pulse" /></div>
      <h2 className="serif-h loading-title">{label}</h2>
      <p className="body loading-sub">{sub}</p>
    </div>
  );
}
window.Loading = Loading;

// Combine several uploaded résumé profiles into one. Lists (education,
// experience, projects, skills, …) are concatenated and de-duped; nested objects
// are merged; plain scalars (name, email, …) take the first non-empty value, so
// the first selected résumé is the primary for those. This lets the AI see the
// union of everything across the selected résumés.
function _mergeValue(a, b) {
  if (Array.isArray(a) || Array.isArray(b)) {
    const flat = []
      .concat(Array.isArray(a) ? a : (a != null ? [a] : []))
      .concat(Array.isArray(b) ? b : (b != null ? [b] : []));
    const seen = new Set(), out = [];
    for (const item of flat) {
      if (item == null) continue;
      const sig = (typeof item === 'object') ? JSON.stringify(item) : String(item).trim().toLowerCase();
      if (sig === '' || seen.has(sig)) continue;
      seen.add(sig); out.push(item);
    }
    return out;
  }
  if (a && typeof a === 'object' && b && typeof b === 'object') {
    const out = { ...a };
    for (const k of Object.keys(b)) out[k] = (k in out) ? _mergeValue(out[k], b[k]) : b[k];
    return out;
  }
  return (a != null && String(a).trim() !== '') ? a : b;
}
function mergeProfiles(profiles) {
  const valid = (profiles || []).filter(p => p && typeof p === 'object');
  if (!valid.length) return {};
  return valid.reduce((acc, p) => _mergeValue(acc, p));
}

function App() {
  // Auth / profile state. Restored from localStorage on first render so a
  // signed-in user lands straight on Matches and skips the welcome screen.
  const savedId = localStorage.getItem('userId');
  const savedEmail = localStorage.getItem('userEmail');
  const savedName = localStorage.getItem('userName');
  // Always open on the home page (the "Welcome back" landing). Returning users
  // click through to their dashboard from there rather than being dropped
  // straight into Matches on load.
  const [view, setView] = useState('welcome');
  const [params, setParams] = useState({});
  // Demo mode is OFF by default and has NO in-app switch — it's controlled by
  // the backend (MOCK_MODE), fetched once below. `demoReady` gates the initial
  // match load until we know which mode we're in.
  const [demo, setDemo] = useState(false);
  const [demoReady, setDemoReady] = useState(false);

  const [currentUser, setCurrentUser] = useState(
    savedId ? { user_id: parseInt(savedId, 10), email: savedEmail, name: savedName || null } : null
  );
  const [profile, setProfile] = useState(null);
  const [profileId, setProfileId] = useState(null);

  // One-shot upgrade: earlier builds of this design seeded sample favourites
  // and drafted history into localStorage. Wipe them on first load with this
  // schema version so existing testers don't see stale demo content. Safe to
  // bump SCHEMA_VERSION later if we ever need to do this again.
  const SCHEMA_VERSION = '2026-06-13-clear-seeds';
  if (localStorage.getItem('appSchemaVersion') !== SCHEMA_VERSION) {
    localStorage.removeItem('favIds');
    localStorage.removeItem('drafts');
    localStorage.setItem('appSchemaVersion', SCHEMA_VERSION);
  }

  // Favourites: opportunity ids the user starred. Persisted to localStorage so
  // they survive refresh (until a real backend favourites table is added).
  const [favIds, setFavIds] = useState(() => {
    try { return JSON.parse(localStorage.getItem('favIds') || '{}'); } catch (_) { return {}; }
  });
  useEffect(() => {
    localStorage.setItem('favIds', JSON.stringify(favIds));
  }, [favIds]);

  // History: opportunities the user has drafted application materials for.
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('drafts') || '[]'); } catch (_) { return []; }
  });
  useEffect(() => {
    localStorage.setItem('drafts', JSON.stringify(history));
  }, [history]);

  // Which uploaded résumés are selected to be combined into the active profile.
  // Persisted so the combination survives a refresh.
  const [selectedResumeIds, setSelectedResumeIds] = useState(() => {
    try { return JSON.parse(localStorage.getItem('selectedResumeIds') || '[]'); } catch (_) { return []; }
  });
  useEffect(() => {
    localStorage.setItem('selectedResumeIds', JSON.stringify(selectedResumeIds));
  }, [selectedResumeIds]);

  const [collapsed, setCollapsed] = useState(false);
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);

  // Match results live at App level so the work survives tab switches.
  // Results.jsx reads `matchData` and only fetches when `matchData.hasMatched`
  // is false. Switching to Favourites/History/Account and back to Matches no
  // longer re-runs the 30-second search.
  const [matchData, setMatchData] = useState({
    seedResults: [], liveResults: [],
    seedLoading: false, liveLoading: false,
    // hasMatched: a search has run at least once. searchedSources: which segments
    // ('jobs'/'scholarships') have actually been searched — drives per-segment UI
    // (e.g. the button reads "Search" until that segment has run once).
    hasMatched: false, searchedSources: [], liveNotice: null, pendingSearch: false,
  });

  // True for guest sessions — used to hide auth-only UI (logout button etc.).
  const isGuest = !!sessionStorage.getItem('guestMode');

  // After a profile save in form.jsx, surface a brief "Saved" toast in the app
  // chrome. Cleared automatically a couple of seconds later.
  const [toast, setToast] = useState('');
  const toastTimerRef = useRef(null);
  function showToast(msg) {
    setToast(msg);
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(''), 2200);
  }

  const favCount = Object.keys(favIds).length;
  // Store the FULL opp object (not just `true`) so the Favourites page can
  // render the card even when results.jsx isn't holding the source list.
  function toggleFav(opp) {
    setFavIds(prev => {
      const next = { ...prev };
      if (next[opp.id]) delete next[opp.id]; else next[opp.id] = opp;
      return next;
    });
  }

  const accent = ACCENTS[t.accent] || ACCENTS.gold;
  const atmos = ATMOS[t.atmosphere] || ATMOS.balanced;
  const fanCfg = FANS[t.fanStyle] || FANS.spread;
  const fan = { ...fanCfg, pale: accent.pale, gold: accent.gold };

  useEffect(() => {
    const root = document.documentElement;
    const vars = { ...accent.vars, ...atmos };
    Object.entries(vars).forEach(([k, v]) => root.style.setProperty(k, v));
  }, [t.accent, t.atmosphere]);

  // Demo mode is backend-controlled (MOCK_MODE). Fetch it once on load; there is
  // no in-app switch. Defaults off if the request fails. `demoReady` flips true
  // either way so the matches page knows it can start.
  useEffect(() => {
    window.API.getConfig()
      .then(cfg => { if (cfg && typeof cfg.mock_mode === 'boolean') setDemo(cfg.mock_mode); })
      .catch(() => { /* leave demo off */ })
      .finally(() => setDemoReady(true));
  }, []);

  // On first mount, if the user is signed in, fetch their saved profile so
  // form.jsx / results.jsx have something to work with.
  useEffect(() => {
    if (!currentUser || !currentUser.user_id) return;
    // If the user previously combined specific résumés, re-apply that selection
    // (silently) so the combined profile is restored. Otherwise load their
    // latest single profile.
    if (selectedResumeIds && selectedResumeIds.length) {
      applyResumeSelection(selectedResumeIds, { silent: true });
      return;
    }
    window.API.getUserProfile(currentUser.user_id)
      .then(data => {
        if (data && data.structured_profile) {
          setProfile(data.structured_profile);
          setProfileId(data.profile_id);
        }
      })
      .catch(() => { /* no saved profile yet — fine */ });
  }, []); // mount only

  function onLogin(payload) {
    // Always start each sign-in / sign-up / guest session with a clean slate
    // for favourites + history so a previous user's saved data on the same
    // machine never bleeds into the new account.
    setFavIds({});
    setHistory([]);
    setSelectedResumeIds([]);
    localStorage.removeItem('favIds');
    localStorage.removeItem('drafts');
    localStorage.removeItem('selectedResumeIds');

    if (payload.guest) {
      setCurrentUser(null);
      return;
    }
    setCurrentUser({ user_id: payload.user_id, email: payload.email, name: payload.name });
    if (payload.profile) setProfile(payload.profile);
    if (payload.profile_id) setProfileId(payload.profile_id);
  }

  // Account settings saved a name / email change. Update currentUser in place
  // (don't wipe favourites/history the way a fresh login does) and mirror it to
  // localStorage so it survives a reload.
  function onUserUpdate(updated) {
    if (!updated) return;
    setCurrentUser(cu => (cu ? { ...cu, name: updated.name, email: updated.email } : cu));
    if (updated.name != null) localStorage.setItem('userName', updated.name);
    if (updated.email != null) localStorage.setItem('userEmail', updated.email);
  }

  function onProfileSaved(payload) {
    if (payload.profile) setProfile(payload.profile);
    if (payload.profile_id) setProfileId(payload.profile_id);
  }

  // Set which uploaded résumés are combined into the active profile. Fetches the
  // selected profiles, merges them into one, and uses the result for matching +
  // tailored generation. `opts.silent` skips the toast + match reset (used when
  // re-applying a persisted selection on mount).
  async function applyResumeSelection(idList, opts = {}) {
    const list = idList || [];
    setSelectedResumeIds(list);
    if (!list.length) return;
    try {
      const fetched = await Promise.all(list.map(id =>
        window.API.getProfile(id).then(d => (d && d.structured_profile) || null).catch(() => null)
      ));
      const valid = fetched.filter(Boolean);
      if (!valid.length) return;
      const merged = valid.length === 1 ? valid[0] : mergeProfiles(valid);
      setProfile(merged);
      setProfileId(list.length === 1 ? list[0] : null); // a combined profile has no single id
      if (!opts.silent) {
        setMatchData({ seedResults: [], liveResults: [], seedLoading: false, liveLoading: false, hasMatched: false, searchedSources: [], liveNotice: null });
        showToast(list.length === 1 ? 'Using this résumé' : `Combining ${list.length} résumés`);
      }
    } catch (_) { /* keep the current profile if a fetch fails */ }
  }

  function go(next, p = {}) {
    // Log a drafted application into History (newest first, de-duped by id).
    if (next === 'application' && p.job) {
      const j = p.job;
      const entry = {
        id: j.id || j.role, role: j.role, org: j.org, source: j.source || 'indeed',
        date: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      };
      setHistory(h => [entry, ...h.filter(x => x.id !== entry.id)]);
    }
    setParams(p);
    setView(next);
    window.scrollTo({ top: 0, behavior: 'auto' });
  }

  // Called by form.jsx when the user clicks "Find my matches". `nextProfile`
  // is the just-built profile, also stored in App state so Results can read it.
  // Clearing matchData forces Results.jsx to re-fetch — exactly what we want
  // here, because the user just edited their profile.
  function runMatch(nextProfile) {
    if (nextProfile) setProfile(nextProfile);
    // pendingSearch tells the Matches page to run one search on arrival — the
    // user explicitly asked to find matches. Plain tab navigation never sets it,
    // so entering Matches otherwise does not auto-search.
    setMatchData({ seedResults: [], liveResults: [], seedLoading: false, liveLoading: false, hasMatched: false, searchedSources: [], liveNotice: null, pendingSearch: true });
    go('matches');
  }

  function logout() {
    // Sign out wipes everything: user + profile, favourites, drafted history,
    // cached match results, and their localStorage copies. The next visitor
    // starts from zero.
    localStorage.removeItem('userId');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userName');
    localStorage.removeItem('favIds');
    localStorage.removeItem('drafts');
    sessionStorage.removeItem('guestMode');
    setCurrentUser(null);
    setProfile(null);
    setProfileId(null);
    setFavIds({});
    setHistory([]);
    setSelectedResumeIds([]);
    localStorage.removeItem('selectedResumeIds');
    setMatchData({ seedResults: [], liveResults: [], seedLoading: false, liveLoading: false, hasMatched: false, searchedSources: [], liveNotice: null });
    go('welcome');
  }

  const accentKeys = ['gold', 'citrus', 'ember', 'sage'];
  const accentColors = accentKeys.map(k => ACCENTS[k].vars['--gold-paper']);
  const panel = (
    <TweaksPanel>
      <TweakSection label="Accent" />
      <TweakColor label="Color" value={accent.vars['--gold-paper']} options={accentColors}
        onChange={(c) => setTweak('accent', accentKeys.find(k => ACCENTS[k].vars['--gold-paper'].toLowerCase() === String(c).toLowerCase()) || 'gold')} />
      <TweakSection label="Atmosphere" />
      <TweakRadio label="Surface" value={t.atmosphere} options={['airy', 'balanced', 'grounded']}
        onChange={(v) => setTweak('atmosphere', v)} />
      <TweakSection label="Paper fan" />
      <TweakRadio label="Spread" value={t.fanStyle} options={['tight', 'spread', 'lavish']}
        onChange={(v) => setTweak('fanStyle', v)} />
    </TweaksPanel>
  );

  const user = currentUser
    ? { name: currentUser.name || (currentUser.email || '').split('@')[0] || 'Friend', email: currentUser.email }
    : { name: 'Guest' };

  let content;
  if (view === 'welcome') content = <Welcome go={go} fan={fan} currentUser={currentUser} isGuest={isGuest} />;
  else if (view === 'auth') content = <Auth go={go} mode={params.mode || 'signin'} fan={fan} onLogin={onLogin} />;
  else {
    // In-app views share the sidebar shell. Application stays under the
    // "Matches" sidebar group because that's the flow that brought the user
    // here — clicking Draft from a match shouldn't dim the Matches item and
    // light up History instead.
    const sectionFor = {
      form: 'upload', uploads: 'uploads', resumes: 'resumes', matches: 'matches',
      favourites: 'favourites', history: 'history', application: 'matches',
      appdetail: 'resumes', account: 'account',
    };
    const section = sectionFor[view] || 'matches';
    let inner;
    if (view === 'form') inner = <ProfileForm go={go} runMatch={runMatch} currentUser={currentUser} initialProfile={profile} onProfileSaved={onProfileSaved} demo={demo} showToast={showToast} />;
    else if (view === 'uploads') inner = <MyResumes go={go} currentUser={currentUser} demo={demo} selectedIds={selectedResumeIds} onApply={applyResumeSelection} />;
    else if (view === 'resumes') inner = <MyApplications go={go} currentUser={currentUser} />;
    else if (view === 'matches') inner = <Results go={go} favIds={favIds} toggleFav={toggleFav} profile={profile} demo={demo} demoReady={demoReady} matchData={matchData} setMatchData={setMatchData} />;
    else if (view === 'favourites') inner = <Favourites go={go} favIds={favIds} toggleFav={toggleFav} />;
    else if (view === 'history') inner = <HistoryView go={go} history={history} />;
    else if (view === 'account') inner = <AccountSettings go={go} user={user} currentUser={currentUser} onUserUpdate={onUserUpdate} showToast={showToast} onLogout={logout} isGuest={isGuest} />;
    else if (view === 'application') inner = <Application go={go} job={params.job} profile={profile} demo={demo} currentUser={currentUser} showToast={showToast} key={`a-${params.job && params.job.id}`} />;
    else if (view === 'appdetail') inner = <Application go={go} appId={params.appId} demo={demo} currentUser={currentUser} showToast={showToast} key={`d-${params.appId}`} />;
    else inner = <Results go={go} favIds={favIds} toggleFav={toggleFav} profile={profile} demo={demo} demoReady={demoReady} matchData={matchData} setMatchData={setMatchData} />;

    content = (
      <div className={"app-shell" + (collapsed ? ' nav-collapsed' : '')}>
        <Sidebar section={section} user={user} go={go} favCount={favCount}
          collapsed={collapsed} onToggleCollapse={() => setCollapsed(c => !c)} />
        <div className="app-main app-page">
          <div className="topstrip">
            <span className="topbar-mode">{demo ? 'Demo mode' : 'Searches LIVE results'}</span>
          </div>
          {inner}
        </div>
      </div>
    );
  }

  // Floating "Saved" toast — visible above all views, briefly.
  const toastEl = toast ? (
    <div className="app-toast" role="status" aria-live="polite">{toast}</div>
  ) : null;

  return (<React.Fragment>{content}{panel}{toastEl}</React.Fragment>);
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
