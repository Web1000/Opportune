// Auth — sign in / sign up. Editorial split: brand panel + form.
// On submit, calls POST /login with mode="signin"|"signup". Stores the returned
// user_id + email + name in localStorage so the next page-load skips welcome.
function Auth({ go, mode, fan = {}, onLogin }) {
  const [m, setM] = useState(mode || 'signin');
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr('');
    const cleanEmail = email.trim();
    if (!cleanEmail || !cleanEmail.includes('@')) {
      setErr('Please enter a valid email.');
      return;
    }
    if (m === 'signup' && !name.trim()) {
      setErr('Please enter your name to sign up.');
      return;
    }
    setBusy(true);
    try {
      const data = await window.API.login(cleanEmail, m, m === 'signup' ? name.trim() : undefined);
      // Persist for next page-load.
      localStorage.setItem('userId', String(data.user_id));
      localStorage.setItem('userEmail', data.email);
      if (data.name) localStorage.setItem('userName', data.name);
      else localStorage.removeItem('userName');
      sessionStorage.removeItem('guestMode');
      // Hand control back to App so it can hydrate any saved profile.
      if (onLogin) onLogin({ user_id: data.user_id, email: data.email, name: data.name, profile: data.structured_profile, profile_id: data.profile_id });
      go(data.structured_profile ? 'matches' : 'form');
    } catch (e) {
      setErr(e.message || 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  function guest() {
    sessionStorage.setItem('guestMode', '1');
    localStorage.removeItem('userId');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userName');
    if (onLogin) onLogin({ guest: true });
    go('form');
  }

  return (
    <div className="auth">
      <aside className="auth-aside">
        <div className="auth-aside-top">
          <span className="logo" onClick={() => go('welcome')} style={{ cursor: 'pointer' }}>Opportune</span>
        </div>
        <div className="auth-aside-body">
          <h2 className="display auth-aside-title">Your future.<br />Fully matched.</h2>
          <p className="lede auth-aside-sub">Keep your profile and matches across sessions — pick up exactly where you left off.</p>
        </div>
        <div className="auth-aside-fan"><PaperFan count={14} animate={false} pale={fan.pale} gold={fan.gold} /></div>
      </aside>

      <main className="auth-main">
        <div className="auth-card">
          <p className="eyebrow">Welcome</p>
          <h1 className="serif-h auth-title">{m === 'signin' ? 'Sign in to Opportune' : 'Create your account'}</h1>
          <p className="body auth-lede">
            {m === 'signin'
              ? 'Sign in to keep your profile and matches across sessions, or continue as a guest to try it out.'
              : 'Set up an account to save your profile, matches, and drafted materials.'}
          </p>

          <div className="seg">
            <button className={"seg-btn" + (m === 'signin' ? ' on' : '')} onClick={() => { setM('signin'); setErr(''); }}>Sign in</button>
            <button className={"seg-btn" + (m === 'signup' ? ' on' : '')} onClick={() => { setM('signup'); setErr(''); }}>Sign up</button>
          </div>

          <form className="auth-form" onSubmit={submit}>
            {m === 'signup' && (
              <div className="field">
                <label className="field-label">Full name</label>
                <input className="input" placeholder="Alex Chen" value={name} onChange={e => setName(e.target.value)} autoComplete="name" />
              </div>
            )}
            <div className="field">
              <label className="field-label">Email</label>
              <input className="input" type="email" placeholder="demo@example.com" value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" />
            </div>
            {err && (
              <p className="body" style={{ color: '#b14a2a', background: '#fbe7d8', padding: '8px 12px', borderRadius: 8, fontSize: '.9rem', marginTop: 4 }}>{err}</p>
            )}
            <button className="btn btn-primary auth-submit" type="submit" disabled={busy}>
              {busy ? (m === 'signup' ? 'Creating account…' : 'Signing in…') : 'Continue'}
            </button>
          </form>

          <div className="auth-or"><span>or</span></div>
          <button className="btn-text auth-guest" onClick={guest}>Continue as guest →</button>
        </div>
      </main>
    </div>
  );
}
window.Auth = Auth;
