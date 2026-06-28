// Profile form — "Your info" tab.
// Controlled state for every field so submit can build the backend-shape
// profile and send it through window.API. Upload résumé wires the button to
// a real file input that posts to /upload-resume and auto-fills the form
// from the parsed result.
function Chevron({ open }) {
  return (
    <svg className={"chev" + (open ? ' open' : '')} width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3.5 5.5L7 9l3.5-3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>);

}

function Section({ id, title, hint, open, toggle, addLabel, onAdd, children }) {
  return (
    <section className="fsec">
      <div className="fsec-head" onClick={() => toggle(id)}>
        <div className="fsec-titlewrap">
          <h3 className="serif-h fsec-title">{title} <Chevron open={open} /></h3>
          {hint && <p className="cap fsec-hint">{hint}</p>}
        </div>
        {addLabel && open &&
        <button className="add-btn" onClick={(e) => {e.stopPropagation();onAdd();}}>+ {addLabel}</button>
        }
      </div>
      {open && <div className="fsec-body">{children}</div>}
    </section>);

}

function Field({ label, value, onChange, ...rest }) {
  return (
    <div className="field">
      <label className="field-label" style={{ margin: "0px 0px 8px" }}>{label}</label>
      <input className="input" value={value == null ? '' : value} onChange={(e) => onChange && onChange(e.target.value)} {...rest} />
    </div>);

}

// Convert this component's local state into the shape the Flask backend expects.
function buildProfileForBackend(s) {
  return {
    name: s.name,
    email: s.email,
    phone: s.phone,
    location: s.location,
    links: { linkedin: s.linkedin, github: s.github },
    education: s.edu.filter(e => e.school || e.degree || e.gpa).map(e => ({
      school: e.school, degree: e.degree, gpa: e.gpa, year: e.year, location: '',
    })),
    skills: { languages: s.skills, tools: [], web: [] },
    interests: s.interests,
    experiences: s.exp.filter(e => e.role || e.org || e.detail).map(e => ({
      category: 'Work', title: e.role, organization: e.org,
      location: '', duration: e.when, description: e.detail,
    })),
    projects: s.projects.filter(p => p.name || p.detail).map(p => ({
      name: p.name, technologies: [], description: p.detail,
    })),
    awards: s.awards.filter(a => a && a.trim()),
  };
}

// Hydrate this component's local state from a backend profile (e.g. on login
// or after PDF parse). Tolerates the older flat skills array shape too.
function backendProfileToFormState(p) {
  if (!p) return null;
  const skillsRaw = p.skills;
  let skills = [];
  if (Array.isArray(skillsRaw)) skills = skillsRaw;
  else if (skillsRaw && typeof skillsRaw === 'object') {
    skills = []
      .concat(skillsRaw.languages || [])
      .concat(skillsRaw.tools || [])
      .concat(skillsRaw.web || []);
  }
  return {
    name: p.name || '',
    email: p.email || '',
    phone: p.phone || '',
    location: p.location || '',
    linkedin: (p.links && p.links.linkedin) || '',
    github: (p.links && p.links.github) || '',
    edu: (p.education && p.education.length ? p.education : [{}]).map(e => ({
      school: e.school || '', degree: e.degree || '', year: e.year || '', gpa: e.gpa || '',
    })),
    skills,
    interests: p.interests || [],
    exp: (p.experiences && p.experiences.length ? p.experiences : [{}]).map(e => ({
      role: e.title || '', org: e.organization || '', when: e.duration || '', detail: e.description || '',
    })),
    projects: (p.projects && p.projects.length ? p.projects : [{}]).map(pp => ({
      name: pp.name || '', detail: pp.description || '',
    })),
    awards: p.awards || [],
  };
}

function ProfileForm({ go, runMatch, currentUser, initialProfile, onProfileSaved, demo, showToast }) {
  const [open, setOpen] = useState({ contact: true, education: true, skills: true, interests: true, experience: true, projects: false, awards: true });
  const toggle = (id) => setOpen((o) => ({ ...o, [id]: !o[id] }));

  // Fresh users start completely empty — no seed skills, interests, or awards.
  // The form fills itself in only after the user uploads a résumé or types.
  const defaults = backendProfileToFormState(initialProfile) || {
    name: '', email: '', phone: '', location: '', linkedin: '', github: '',
    edu: [{ school: '', degree: '', year: '', gpa: '' }],
    skills: [],
    interests: [],
    awards: [],
    exp: [{ role: '', org: '', when: '', detail: '' }],
    projects: [{ name: '', detail: '' }],
  };

  const [name, setName] = useState(defaults.name);
  const [email, setEmail] = useState(defaults.email);
  const [phone, setPhone] = useState(defaults.phone);
  const [location, setLocation] = useState(defaults.location);
  const [linkedin, setLinkedin] = useState(defaults.linkedin);
  const [github, setGithub] = useState(defaults.github);
  const [edu, setEdu] = useState(defaults.edu);
  const [skills, setSkills] = useState(defaults.skills);
  const [skillInput, setSkillInput] = useState('');
  const [interests, setInterests] = useState(defaults.interests);
  const [interestInput, setInterestInput] = useState('');
  const [exp, setExp] = useState(defaults.exp);
  const [projects, setProjects] = useState(defaults.projects);
  const [awards, setAwards] = useState(defaults.awards);

  const [parsing, setParsing] = useState(false);
  const [parseStatus, setParseStatus] = useState('');
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState(null); // Date | null, drives the subtle indicator
  const [autosaveError, setAutosaveError] = useState('');
  const [showEmptyAlert, setShowEmptyAlert] = useState(false);
  const fileInputRef = useRef(null);

  // Autosave bookkeeping. We debounce field changes by ~800ms so a burst of
  // typing collapses into one network round-trip. The very first render is
  // skipped (no point saving the form that was just hydrated from the user's
  // own data) and so is any state change that originated from a PDF upload
  // (handled by suppressing the next autosave with skipNextAutosaveRef).
  const autosaveTimerRef = useRef(null);
  const skipNextAutosaveRef = useRef(true); // skip the initial-hydration save
  const inFlightSaveRef = useRef(null);     // tracks the currently running save promise
  // The profile object this form last echoed up via onProfileSaved. App stores
  // it verbatim and passes it back as initialProfile; without this guard the
  // hydrate effect below would re-run on that echo and wipe an in-progress
  // empty entry the user just added (it gets filtered out of the saved copy).
  const lastSavedRef = useRef(null);

  // If the user logs in mid-session and a profile arrives later, hydrate.
  // Hydrating is NOT a user edit, so skip the next autosave it would trigger.
  useEffect(() => {
    if (!initialProfile) return;
    if (initialProfile === lastSavedRef.current) return; // our own autosave echo — don't clobber local edits
    const s = backendProfileToFormState(initialProfile);
    if (!s) return;
    skipNextAutosaveRef.current = true;
    setName(s.name); setEmail(s.email); setPhone(s.phone); setLocation(s.location);
    setLinkedin(s.linkedin); setGithub(s.github);
    setEdu(s.edu.length ? s.edu : [{}]);
    setSkills(s.skills); setInterests(s.interests);
    setExp(s.exp.length ? s.exp : [{}]);
    setProjects(s.projects.length ? s.projects : [{}]);
    setAwards(s.awards);
  }, [initialProfile]);

  // ── Autosave: debounced save whenever any field changes. ──────────────
  // Runs the save ~800ms after the user stops typing, so a burst of edits
  // becomes a single network round-trip. The "Saved" indicator next to the
  // page title tells the user the latest version is on the server.
  async function doSave(profileDict) {
    setSaving(true);
    setAutosaveError('');
    try {
      const userId = currentUser && currentUser.user_id;
      const saved = await window.API.saveProfile(profileDict, userId);
      lastSavedRef.current = profileDict;   // so the echo back from App doesn't re-hydrate us
      if (onProfileSaved) onProfileSaved({ profile: profileDict, profile_id: saved.profile_id });
      setSavedAt(new Date());
    } catch (e) {
      console.warn('Autosave failed:', e);
      setAutosaveError(e.message || 'Save failed');
    } finally {
      setSaving(false);
      inFlightSaveRef.current = null;
    }
  }

  useEffect(() => {
    if (skipNextAutosaveRef.current) {
      skipNextAutosaveRef.current = false;
      return;
    }
    clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => {
      const profileDict = buildProfileForBackend({
        name, email, phone, location, linkedin, github, edu, skills, interests, exp, projects, awards,
      });
      inFlightSaveRef.current = doSave(profileDict);
    }, 800);
    return () => clearTimeout(autosaveTimerRef.current);
  }, [name, email, phone, location, linkedin, github, edu, skills, interests, exp, projects, awards]);

  function addSkill(e) {
    e.preventDefault();
    const v = skillInput.trim();
    if (v && !skills.includes(v)) setSkills([...skills, v]);
    setSkillInput('');
  }

  function addInterest(e) {
    e.preventDefault();
    const v = interestInput.trim();
    if (v && !interests.includes(v)) setInterests([...interests, v]);
    setInterestInput('');
  }

  // Upload résumé: open the file picker, then POST it to /upload-resume.
  function openUpload() {
    if (fileInputRef.current) fileInputRef.current.click();
  }

  async function onFileChosen(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    console.log('[upload] picked file:', file.name, file.size, 'bytes');
    setParsing(true);
    setParseStatus(demo ? 'Loading sample profile…' : 'Reading your résumé…');
    try {
      const data = await window.API.uploadResume(file, currentUser && currentUser.user_id, demo);
      console.log('[upload] backend returned:', data);
      const sp = data && data.structured_profile;
      if (!sp || typeof sp !== 'object') {
        throw new Error('Backend returned no structured_profile');
      }
      // profile_service.py catches its own exceptions (rate limit, API
      // errors, malformed JSON from the model) and returns an empty profile
      // shape with an `error` field set. Surface that as a real failure
      // instead of pretending the fields were filled in.
      if (sp.error) {
        const reason = String(sp.error);
        // Match the most common cases so we can show a friendlier line.
        if (/api.?key|unauthor|401|403/i.test(reason)) {
          throw new Error("Hack Club AI key missing or invalid — set HACKCLUB_AI_API_KEY on the server (or have an admin enable demo mode).");
        }
        if (/rate.?limit|429/i.test(reason)) {
          throw new Error("The model is rate-limited right now. Wait a minute and try again.");
        }
        throw new Error(reason);
      }
      const s = backendProfileToFormState(sp);
      console.log('[upload] converted to form state:', s);
      if (!s) throw new Error('Could not convert structured_profile');

      // Open EVERY collapsible section so the user can immediately see the
      // freshly-filled fields. Previously the Projects section was collapsed
      // by default, so a user who didn't expand it would think the parse
      // failed — even though the data was already in state.
      setOpen({ contact: true, education: true, skills: true, interests: true, experience: true, projects: true, awards: true });

      // /upload-resume already persisted the parsed profile server-side, so
      // skip the autosave the upcoming setState() burst would otherwise
      // trigger — saving again would be a wasted round-trip.
      skipNextAutosaveRef.current = true;
      setName(s.name); setEmail(s.email); setPhone(s.phone); setLocation(s.location);
      setLinkedin(s.linkedin); setGithub(s.github);
      setEdu(s.edu.length ? s.edu : [{}]);
      setSkills(s.skills); setInterests(s.interests);
      setExp(s.exp.length ? s.exp : [{}]);
      setProjects(s.projects.length ? s.projects : [{}]);
      setAwards(s.awards);

      setParseStatus(data.profile_id
        ? `Filled in for you — saved as Profile #${data.profile_id}`
        : 'Filled in for you — edit anything you want.');
      if (onProfileSaved) onProfileSaved({ profile: sp, profile_id: data.profile_id });
      setSavedAt(new Date());
    } catch (err) {
      console.error('[upload] failed:', err);
      setParseStatus("Couldn't parse the résumé: " + (err.message || err));
    } finally {
      setParsing(false);
      e.target.value = ''; // allow re-uploading the same file
    }
  }

  // Find my matches. If the form is completely empty, pop the alert modal
  // instead of running a search that would score against nothing. Otherwise
  // flush any pending autosave so matching uses the latest values.
  async function handleFindMatches() {
    if (!hasAnyContent) {
      setShowEmptyAlert(true);
      return;
    }
    const profile = buildProfileForBackend({
      name, email, phone, location, linkedin, github, edu, skills, interests, exp, projects, awards,
    });
    clearTimeout(autosaveTimerRef.current);
    if (inFlightSaveRef.current) {
      try { await inFlightSaveRef.current; } catch (_) { /* surfaced by autosave UI */ }
    }
    try {
      await doSave(profile);
    } catch (_) { /* doSave handles its own error UI */ }
    runMatch(profile);
  }

  // Short, calm autosave status — sits just under the lede so the user can
  // always glance up and know their edits are in the system.
  let autosaveLabel = '';
  if (autosaveError) autosaveLabel = 'Couldn\'t save · ' + autosaveError;
  else if (saving) autosaveLabel = 'Saving…';
  else if (savedAt) autosaveLabel = 'Saved';

  // Matching against a blank profile would give meaningless scores, so block
  // the CTA until the user has put SOMETHING in. Any contact field, any
  // skill / interest / award, or any non-empty education / experience /
  // project entry counts.
  const hasAnyContent = !!(
    name.trim() || email.trim() || phone.trim() || location.trim() ||
    linkedin.trim() || github.trim() ||
    skills.length || interests.length || awards.some(a => (a || '').trim()) ||
    edu.some(e => (e.school || e.degree || e.gpa || e.year || '').toString().trim()) ||
    exp.some(e => (e.role || e.org || e.when || e.detail || '').toString().trim()) ||
    projects.some(p => (p.name || p.detail || '').toString().trim())
  );

  return (
    <div className="page-shell">
      <header className="page-head">
        <p className="eyebrow gold">Application season, simplified</p>
        <h1 className="display page-title">AI Opportunity Matcher</h1>
        <p className="lede page-lede">Applications are exhausting. Hand over your résumé and let it do the rest — find the matches, show what's missing, and draft the materials.</p>
        {autosaveLabel && (
          <p className={"autosave-status" + (autosaveError ? ' autosave-err' : (saving ? ' autosave-saving' : ' autosave-saved'))}>
            {!saving && !autosaveError && (
              <svg className="autosave-tick" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7" /></svg>
            )}
            {autosaveLabel}
          </p>
        )}
      </header>

      <input ref={fileInputRef} type="file" accept="application/pdf" onChange={onFileChosen} style={{ display: 'none' }} />

      <div className="parse-block">
        <span className="parse-ic">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 15V4M8 8l4-4 4 4" /><path d="M5 14v5a1 1 0 001 1h12a1 1 0 001-1v-5" />
          </svg>
        </span>
        <h3 className="serif-h parse-block-title">Upload your résumé</h3>
        <p className="body parse-block-sub">{parsing ? parseStatus : (parseStatus || "Drop a PDF here and we'll autofill everything below — or fill it in by hand.")}</p>
        <button className="btn btn-gold parse-block-btn" onClick={openUpload} disabled={parsing}>
          {parsing ? 'Reading…' : 'Upload résumé'}
        </button>
      </div>

      <Section id="contact" title="Contact" open={open.contact} toggle={toggle}>
        <div className="grid-2">
          <Field label="Full name" value={name} onChange={setName} placeholder="Alex Chen" />
          <Field label="Email" value={email} onChange={setEmail} placeholder="alex@example.com" type="email" />
          <Field label="Phone" value={phone} onChange={setPhone} placeholder="+1 (555) 123-4567" />
          <Field label="Location" value={location} onChange={setLocation} placeholder="Toronto, ON" />
          <Field label="LinkedIn" value={linkedin} onChange={setLinkedin} placeholder="linkedin.com/in/…" />
          <Field label="GitHub" value={github} onChange={setGithub} placeholder="github.com/…" />
        </div>
      </Section>

      <hr className="hr" />

      <Section id="education" title="Education" hint="Schools, degrees, GPA, graduation year." open={open.education} toggle={toggle}
      addLabel="Add" onAdd={() => setEdu([...edu, { school: '', degree: '', year: '', gpa: '' }])}>
        {edu.map((e, i) =>
        <div className="entry" key={i}>
            {edu.length > 1 && <button className="entry-x" onClick={() => setEdu(edu.filter((_, j) => j !== i))}>×</button>}
            <div className="grid-2">
              <Field label="School" value={e.school} onChange={v => setEdu(edu.map((x, j) => j === i ? { ...x, school: v } : x))} placeholder="University name" />
              <Field label="Degree" value={e.degree} onChange={v => setEdu(edu.map((x, j) => j === i ? { ...x, degree: v } : x))} placeholder="B.Sc. …" />
              <Field label="Graduation" value={e.year} onChange={v => setEdu(edu.map((x, j) => j === i ? { ...x, year: v } : x))} placeholder="2026" />
              <Field label="GPA" value={e.gpa} onChange={v => setEdu(edu.map((x, j) => j === i ? { ...x, gpa: v } : x))} placeholder="3.8 / 4.0" />
            </div>
          </div>
        )}
      </Section>

      <hr className="hr" />

      <Section id="skills" title="Technical skills" hint="Languages, tools, frameworks." open={open.skills} toggle={toggle}>
        <div className="chips">
          {skills.map((s, i) =>
          <span className="chip" key={i}>{s}<button className="chip-x" onClick={() => setSkills(skills.filter((_, j) => j !== i))}>×</button></span>
          )}
        </div>
        <form className="chip-add" onSubmit={addSkill}>
          <input className="input" placeholder="Add a skill and press Enter" value={skillInput} onChange={(e) => setSkillInput(e.target.value)} />
        </form>
      </Section>

      <hr className="hr" />

      <Section id="interests" title="Interests" hint="Fields and topics you want to work in — used to find live matches." open={open.interests} toggle={toggle}>
        <div className="chips">
          {interests.map((s, i) =>
          <span className="chip" key={i}>{s}<button className="chip-x" onClick={() => setInterests(interests.filter((_, j) => j !== i))}>×</button></span>
          )}
        </div>
        <form className="chip-add" onSubmit={addInterest}>
          <input className="input" placeholder="Add an interest and press Enter" value={interestInput} onChange={(e) => setInterestInput(e.target.value)} />
        </form>
      </Section>

      <hr className="hr" />

      <Section id="experience" title="Experience" hint="Jobs, internships, volunteering, leadership." open={open.experience} toggle={toggle}
      addLabel="Add" onAdd={() => setExp([...exp, { role: '', org: '', when: '', detail: '' }])}>
        {exp.map((e, i) =>
        <div className="entry" key={i}>
            {exp.length > 1 && <button className="entry-x" onClick={() => setExp(exp.filter((_, j) => j !== i))}>×</button>}
            <div className="grid-2">
              <Field label="Role" value={e.role} onChange={v => setExp(exp.map((x, j) => j === i ? { ...x, role: v } : x))} placeholder="Software Engineer Intern" />
              <Field label="Organization" value={e.org} onChange={v => setExp(exp.map((x, j) => j === i ? { ...x, org: v } : x))} placeholder="Company" />
            </div>
            <Field label="When" value={e.when} onChange={v => setExp(exp.map((x, j) => j === i ? { ...x, when: v } : x))} placeholder="Summer 2025" />
            <div className="field">
              <label className="field-label">What you did</label>
              <textarea className="input" rows="3" value={e.detail || ''} onChange={ev => setExp(exp.map((x, j) => j === i ? { ...x, detail: ev.target.value } : x))} placeholder="Describe the impact…" />
            </div>
          </div>
        )}
      </Section>

      <hr className="hr" />

      <Section id="projects" title="Projects" hint="Personal or course projects." open={open.projects} toggle={toggle}
      addLabel="Add" onAdd={() => setProjects([...projects, { name: '', detail: '' }])}>
        {projects.map((p, i) =>
        <div className="entry" key={i}>
            {projects.length > 1 && <button className="entry-x" onClick={() => setProjects(projects.filter((_, j) => j !== i))}>×</button>}
            <Field label="Project" value={p.name} onChange={v => setProjects(projects.map((x, j) => j === i ? { ...x, name: v } : x))} placeholder="Project name" />
            <div className="field">
              <label className="field-label">Description</label>
              <textarea className="input" rows="2" value={p.detail || ''} onChange={ev => setProjects(projects.map((x, j) => j === i ? { ...x, detail: ev.target.value } : x))} placeholder="What it does, what you built…" />
            </div>
          </div>
        )}
      </Section>

      <hr className="hr" />

      <Section id="awards" title="Awards & honors" hint="Scholarships, hackathon wins, recognitions." open={open.awards} toggle={toggle}
      addLabel="Add" onAdd={() => setAwards([...awards, ''])}>
        {awards.length === 0 && <p className="cap" style={{ padding: '4px 0 8px' }}>Nothing added yet.</p>}
        {awards.map((a, i) =>
        <div className="entry" key={i}>
            <button className="entry-x" onClick={() => setAwards(awards.filter((_, j) => j !== i))}>×</button>
            <Field label={'Award ' + (i + 1)} value={a} onChange={v => setAwards(awards.map((x, j) => j === i ? v : x))} placeholder="e.g. Dean's Honour List (2024)" />
          </div>
        )}
      </Section>

      <div className="form-cta">
        <button className="btn btn-gold form-cta-btn" onClick={handleFindMatches}>
          Find my matches
        </button>
        <p className="cap form-cta-note">We'll score live opportunities against your profile.</p>
      </div>

      {showEmptyAlert && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="empty-alert-title" onClick={() => setShowEmptyAlert(false)}>
          <div className="modal-card" onClick={e => e.stopPropagation()}>
            <h3 id="empty-alert-title" className="serif-h modal-title">No info to match against</h3>
            <p className="body modal-body">
              Fill in at least one detail — your name, a skill, or any entry below — and we'll have something to score opportunities against.
            </p>
            <div className="modal-actions">
              <button className="btn btn-gold" onClick={() => setShowEmptyAlert(false)}>Got it</button>
            </div>
          </div>
        </div>
      )}
    </div>);

}
window.ProfileForm = ProfileForm;
