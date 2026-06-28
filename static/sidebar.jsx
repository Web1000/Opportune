// Left sidebar — primary navigation, collapsible, visible on all in-app pages.
function NavIcon({ name }) {
  const p = {
    upload: <React.Fragment><path d="M12 15V4M8 8l4-4 4 4" /><path d="M5 14v5a1 1 0 001 1h12a1 1 0 001-1v-5" /></React.Fragment>,
    resumes: <React.Fragment><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M9.5 12h6M9.5 15.5h6" /></React.Fragment>,
    uploads: <React.Fragment><rect x="8" y="4" width="11" height="13" rx="1.5" /><path d="M16 17v2a1 1 0 01-1 1H6a1 1 0 01-1-1V8a1 1 0 011-1h2" /></React.Fragment>,
    matches: <path d="M4 5h7v7H4zM13 5h7v4h-7zM13 12h7v7h-7zM4 15h7v5H4z" />,
    favourites: <path d="M12 3.6l2.6 5.3 5.8.85-4.2 4.1 1 5.8L12 16.9l-5.2 2.75 1-5.8-4.2-4.1 5.8-.85z" />,
    history: <React.Fragment><path d="M3.5 12a8.5 8.5 0 108.5-8.5A8.5 8.5 0 005 7" /><path d="M5 3v4h4" /><path d="M12 7.5V12l3 2" /></React.Fragment>,
    account: <path d="M12 12.5a3.6 3.6 0 100-7.2 3.6 3.6 0 000 7.2zM5.5 20c.6-3.2 3.2-5 6.5-5s5.9 1.8 6.5 5" />,
  }[name];
  return (
    <svg className="nav-ic" width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {p}
    </svg>
  );
}

function Sidebar({ section, user, go, favCount = 0, collapsed, onToggleCollapse }) {
  const items = [
    { id: 'upload', label: 'Your info', view: 'form' },
    { id: 'uploads', label: 'My resumes', view: 'uploads' },
    { id: 'resumes', label: 'My applications', view: 'resumes' },
    { id: 'matches', label: 'Matches', view: 'matches' },
    { id: 'favourites', label: 'Favourites', view: 'favourites', badge: favCount },
    { id: 'history', label: 'History', view: 'history' },
  ];
  const name = user && user.name ? user.name : 'Guest';
  const initials = name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();

  return (
    <aside className="sidebar">
      <div className="sidebar-top">
        <div className="sidebar-brand" onClick={() => go('welcome')}>Opportune</div>
        <button
          className="sidebar-collapse"
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={collapsed ? 'Expand' : 'Collapse'}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d={collapsed ? 'M9 6l6 6-6 6' : 'M15 6l-6 6 6 6'} />
          </svg>
        </button>
      </div>

      <nav className="sidebar-nav">
        {items.map(it => (
          <button
            key={it.id}
            className={"navitem" + (section === it.id ? ' on' : '')}
            onClick={() => go(it.view)}
            title={it.label}>
            <NavIcon name={it.id} />
            <span className="navitem-label">{it.label}</span>
            {it.badge ? <span className="navitem-badge">{it.badge}</span> : null}
          </button>
        ))}
      </nav>

      <div className="sidebar-foot">
        <button
          className={"navitem account-item" + (section === 'account' ? ' on' : '')}
          onClick={() => go('account')}
          title="Account settings">
          <span className="account-avatar">{initials}</span>
          <span className="account-meta">
            <span className="account-name">{name}</span>
            <span className="account-sub">Account settings</span>
          </span>
        </button>
      </div>
    </aside>
  );
}
window.Sidebar = Sidebar;
