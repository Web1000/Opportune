// Welcome / Landing — résumé-as-editorial-object (Concept B).
// When a logged-in user (or active guest) lands here from the in-app logo,
// the auth links collapse into a single "Continue to your dashboard" CTA so
// the page doesn't pretend they're a brand-new visitor.
function Welcome({ go, fan = {}, currentUser, isGuest }) {
  const isAuthed = !!currentUser;
  const isReturning = isAuthed || isGuest;
  const greetingName = isAuthed ? (currentUser.name || (currentUser.email || '').split('@')[0]) : null;

  return (
    <div className="lb">
      <header className="lb-nav">
        <div className="logo">Opportune</div>
        <nav className="lb-navlinks">
          {isReturning ? (
            <React.Fragment>
              {isAuthed && <span className="nav-link" style={{ cursor: 'default', opacity: .75 }}>Signed in as {greetingName}</span>}
              <a className="nav-link" onClick={() => go('matches')}>Continue to dashboard →</a>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <a className="nav-link" onClick={() => go('auth', { mode: 'signin' })}>Sign in</a>
              <a className="nav-link" onClick={() => go('auth', { mode: 'signup' })}>Sign up</a>
              <a className="nav-link" onClick={() => { sessionStorage.setItem('guestMode', '1'); go('form'); }}>Continue as a guest</a>
            </React.Fragment>
          )}
        </nav>
      </header>

      <main className="lb-main">
        <div className="lb-copy">
          <p className="eyebrow lb-eyebrow">AI résumé builder</p>
          <h1 className="lb-title">
            {isAuthed ? <React.Fragment>Welcome back,<br /><em>{greetingName}.</em></React.Fragment>
                      : <React.Fragment>The résumé,<br /><em>written for you.</em></React.Fragment>}
          </h1>
          <p className="lb-sub">
            {isReturning
              ? "Pick up where you left off — your profile, matches, and drafts are all where you saved them."
              : "Hand over your experience once. Opportune drafts a tailored résumé for every role you chase — and shows you exactly why you match."}
          </p>
          <div className="lb-actions">
            {isReturning ? (
              <React.Fragment>
                <button className="btn btn-gold lb-cta" onClick={() => go('matches')}>Go to matches</button>
                <a className="lb-ghostlink" onClick={() => go('form')}>Edit profile <span className="a">→</span></a>
              </React.Fragment>
            ) : (
              <React.Fragment>
                <button className="btn btn-gold lb-cta" onClick={() => go('auth', { mode: 'signup' })}>Build my résumé</button>
                <a className="lb-ghostlink" onClick={() => { sessionStorage.setItem('guestMode', '1'); go('form'); }}>Try as a guest <span className="a">→</span></a>
              </React.Fragment>
            )}
          </div>
        </div>

        <div className="lb-stage">
          <div className="rz-behind"></div>

          <article className="rzcard">
            <div className="rz-top">
              <div>
                <h3 className="rz-name">Alex Chen</h3>
                <p className="rz-role">Senior Software Engineer</p>
              </div>
              <div className="rz-contact">Toronto, ON<br />alex@example.com<br />linkedin.com/in/alexchen</div>
            </div>

            <div className="rz-sec">
              <p className="rz-h">Experience</p>
              <div className="rz-item">
                <div className="rz-item-h"><strong>Founder &amp; Engineer</strong><span>2024 — Present</span></div>
                <p className="rz-org">Opportune</p>
                <ul className="rz-list">
                  <li className="rz-hl"><mark>Built an AI résumé-to-opportunity matcher scoring fit across 1,200+ live roles.</mark></li>
                  <li>Shipped a single-page editorial UI in vanilla HTML, CSS &amp; JS.</li>
                </ul>
              </div>
              <div className="rz-item">
                <div className="rz-item-h"><strong>Software Engineer Intern</strong><span>Summer 2025</span></div>
                <p className="rz-org">Northwind Labs</p>
                <ul className="rz-list">
                  <li>Cut API latency 38% by reworking the caching layer.</li>
                </ul>
              </div>
            </div>

            <div className="rz-sec">
              <p className="rz-h">Skills</p>
              <div className="rz-chips">
                <span>Python</span><span>React</span><span>TypeScript</span><span>SQL</span><span>Flask</span><span>AWS</span>
              </div>
            </div>
          </article>

          <div className="rz-anno rz-anno-match">
            <div className="rz-match-num">94</div>
            <div className="rz-match-cap"><b>% match</b> · Senior PM, Stripe</div>
          </div>

          <div className="rz-anno rz-anno-rewrite">
            <span className="rz-anno-dot"></span>
            <span className="rz-anno-line"></span>
            <span className="rz-anno-label"><span className="rz-anno-kicker">Rewritten ✦</span>Sharpened for impact</span>
          </div>

          <div className="rz-anno rz-anno-skills">
            <span className="rz-anno-dot"></span>
            <span className="rz-anno-line"></span>
            <span className="rz-anno-label"><span className="rz-anno-kicker">Pulled in</span>From your profile</span>
          </div>
        </div>
      </main>

      <div className="welcome-mobilebar">
        {isReturning ? (
          <a className="nav-link" onClick={() => go('matches')}>Continue to dashboard →</a>
        ) : (
          <React.Fragment>
            <a className="nav-link" onClick={() => go('auth', { mode: 'signin' })}>Sign in</a>
            <span className="dot">·</span>
            <a className="nav-link" onClick={() => go('auth', { mode: 'signup' })}>Sign up</a>
          </React.Fragment>
        )}
      </div>
    </div>
  );
}
window.Welcome = Welcome;
