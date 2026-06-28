// Shared API client. Every .jsx component that talks to the Flask backend goes
// through window.API so the call sites stay short and the shapes stay consistent.
//
// All endpoints are same-origin (relative URLs), so this works whether we're on
// localhost:5001 or the deployed Render URL.
//
// Response normalization: the backend's match shape
//   { opportunity: {id, title, organization, type, location, url, source, ...},
//     fit_score, why_good_fit, missing_information, improvement_suggestions }
// is reshaped into the frontend's card shape
//   { id, source, role, org, employment, type, location, deadline, url,
//     score, strengths, missing, suggestions, _raw_opp }
// so cards.jsx / results.jsx / favourites.jsx don't have to think about it.

(function () {
  function json(method, url, body) {
    return fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    }).then(async (r) => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      return data;
    });
  }

  function normalizeMatch(m) {
    const o = (m && m.opportunity) || {};
    const idStr = String(o.id != null ? o.id : Math.random().toString(36).slice(2));
    return {
      id: idStr,
      source: o.source || (o.type === 'Scholarship' ? 'scholarshipscanada' : 'indeed'),
      role: o.title || '',
      org: o.organization || '',
      employment: o.employment_type || '',
      type: o.type || '',
      location: o.location || '',
      deadline: o.deadline || '',
      url: o.url || '#',
      score: m.fit_score || 0,
      strengths: m.why_good_fit || [],
      missing: m.missing_information || [],
      suggestions: m.improvement_suggestions || [],
      live: !!m.live,
      _raw_opp: o, // kept so /generate-application can be called with the original shape
    };
  }

  const API = {
    // ---- Config ----
    // Runtime config from the backend — currently whether demo mode (MOCK_MODE)
    // is on. There is no in-app switch; demo mode is controlled server-side.
    async getConfig() {
      return json('GET', '/config');
    },
    // Update the signed-in user's name / email. Returns { user_id, email, name }.
    async updateUser(userId, fields) {
      return json('PATCH', `/user/${userId}`, fields);
    },

    // ---- Auth ----
    // mode: "signin" | "signup" | undefined (legacy find-or-create)
    async login(email, mode, name) {
      const body = { email };
      if (mode) body.mode = mode;
      if (name) body.name = name;
      return json('POST', '/login', body);
    },

    async getUserProfile(userId) {
      return json('GET', `/user/${userId}/profile`);
    },

    // ---- Profile ----
    async uploadResume(file, userId, mock) {
      const fd = new FormData();
      fd.append('file', file);
      if (mock != null) fd.append('mock', mock ? 'true' : 'false');
      if (userId) fd.append('user_id', String(userId));
      const r = await fetch('/upload-resume', { method: 'POST', body: fd });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
      return data;
    },

    async saveProfile(profileDict, userId) {
      const body = { ...profileDict };
      if (userId) body.user_id = userId;
      return json('POST', '/build-profile-from-form', body);
    },

    async getProfile(profileId) {
      return json('GET', `/profile/${profileId}`);
    },

    // ---- My resumes ----
    async listResumes(userId) {
      const data = await json('GET', `/user/${userId}/resumes`);
      return (data && Array.isArray(data.resumes)) ? data.resumes : [];
    },

    async deleteResume(profileId) {
      return json('DELETE', `/profile/${profileId}`);
    },

    // ---- Matching ----
    async matchOpportunities(profile, mock) {
      const data = await json('POST', '/match-opportunities', { profile, mock: !!mock });
      return (Array.isArray(data) ? data : []).map(normalizeMatch);
    },

    // opts: { sources?: string[], filters?: {company, employment_type}, mock?: bool }.
    // Returns { results: [normalized matches], notice: {...}|null } — notice is set
    // when a company search found nothing and fell back to similar positions.
    async searchLiveOpportunities(profile, opts = {}) {
      const body = { profile, mock: !!opts.mock };
      if (opts.sources) body.sources = opts.sources;
      if (opts.filters) body.filters = opts.filters;
      const data = await json('POST', '/search-live-opportunities', body);
      const list = (data && Array.isArray(data.results)) ? data.results
        : (Array.isArray(data) ? data : []);
      return { results: list.map(normalizeMatch), notice: (data && data.notice) || null };
    },

    // ---- Generation ----
    async generateApplication(profile, opportunity, mock) {
      return json('POST', '/generate-application', { profile, opportunity, mock: !!mock });
    },

    // Saved applications — one per match, upserted by match_key on the backend.
    // Only the fields passed are written, so résumé and cover letter save apart.
    async saveApplication({ userId, matchKey, opportunityName, resumeData, tailoredResume, coverLetter }) {
      const body = { user_id: userId, match_key: matchKey };
      if (opportunityName !== undefined) body.opportunity_name = opportunityName;
      if (resumeData !== undefined) body.resume_data = resumeData;
      if (tailoredResume !== undefined) body.tailored_resume = tailoredResume;
      if (coverLetter !== undefined) body.cover_letter = coverLetter;
      return json('POST', '/save-application', body);
    },

    async listApplications(userId) {
      const data = await json('GET', `/user/${userId}/applications`);
      return (data && Array.isArray(data.applications)) ? data.applications : [];
    },

    async getApplication(id) {
      return json('GET', `/application/${id}`);
    },

    async deleteApplication(id) {
      return json('DELETE', `/application/${id}`);
    },

    // Tries the LaTeX/Tectonic endpoint first; the caller can fall back to
    // jsPDF in the browser if this returns null.
    async renderResumePdf(resumeData, tailoredResume) {
      const r = await fetch('/render-resume-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ resume_data: resumeData, tailored_resume: tailoredResume }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.error || `HTTP ${r.status}`);
      }
      return r.blob();
    },
  };

  window.API = API;
  window.normalizeMatch = normalizeMatch;
})();
