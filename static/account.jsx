// Account settings — profile email, log out.
// In guest mode there is no account to log out of, so the auth-only sections
// (Profile, Sign out) are replaced with a quiet prompt to sign up or sign in.
function AccountSettings({ go, user, currentUser, onUserUpdate, showToast, onLogout, isGuest }) {
  const displayName = user && user.name ? user.name : 'Guest';
  const userId = currentUser && currentUser.user_id;

  // Editable copies of the account fields. Saving PATCHes the user, then refreshes
  // the app's currentUser (+ localStorage) through onUserUpdate so the new name /
  // email show up everywhere (sidebar, etc.).
  const [name, setName] = useState((user && user.name) || '');
  const [email, setEmail] = useState((user && user.email) || '');
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState('');

  async function saveProfile() {
    if (!userId) { go('auth', { mode: 'signin' }); return; }
    setSaving(true); setSaveErr('');
    try {
      const updated = await window.API.updateUser(userId, { name: name.trim(), email: email.trim() });
      if (onUserUpdate) onUserUpdate(updated);
      if (showToast) showToast('Profile updated');
    } catch (e) {
      setSaveErr(e.message || 'Could not save changes.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">Account settings</h1>
        <p className="lede page-lede">
          {isGuest
            ? "You're using Opportune as a guest. Sign in or create an account to save your profile and matches."
            : `Manage your account details for ${displayName}.`}
        </p>
      </header>

      {isGuest ? (
        <section className="acct-sec">
          <h2 className="serif-h acct-title">Account</h2>
          <div className="acct-card">
            <div className="acct-pref">
              <div className="acct-pref-meta">
                <span className="acct-pref-title">No account yet</span>
                <span className="acct-pref-sub">Guests can't save profile changes, favourites, or drafts across sessions.</span>
              </div>
              <button className="btn btn-gold" onClick={() => go('auth', { mode: 'signup' })}>Sign up</button>
            </div>
          </div>
        </section>
      ) : (
        <section className="acct-sec">
          <h2 className="serif-h acct-title">Profile</h2>
          <div className="acct-card">
            <div className="grid-2">
              <Field label="Full name" value={name} onChange={setName} placeholder="Your name" />
              <Field label="Email" value={email} onChange={setEmail} type="email" placeholder="you@example.com" />
            </div>
            {saveErr && <p className="body autosave-err save-note">{saveErr}</p>}
            <div className="acct-row-actions">
              <button className="btn btn-gold" onClick={saveProfile} disabled={saving}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        </section>
      )}

      {!isGuest && (
        <section className="acct-sec">
          <h2 className="serif-h acct-title">Sign out</h2>
          <div className="acct-card acct-danger">
            <div className="acct-pref">
              <div className="acct-pref-meta">
                <span className="acct-pref-title">Log out of Opportune</span>
                <span className="acct-pref-sub">You'll need to sign in again to access your profile.</span>
              </div>
              <button className="btn btn-ghost acct-logout" onClick={() => { if (onLogout) onLogout(); else go('welcome'); }}>Log out</button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
window.AccountSettings = AccountSettings;
