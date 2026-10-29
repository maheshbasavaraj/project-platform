/* ============================================================
   SWE Quiz front-end
   ============================================================ */
const root = '/swe-quiz';
const api = `${root}/api`;
const app = document.querySelector('#app');

const esc = v => String(v ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const get = path => fetch(`${api}${path}`).then(async r => {
  const d = await r.json();
  if (!r.ok) throw Error(d.detail || d.message || 'Request failed');
  return d;
});

const titleise = s => String(s || '').replace(/[-_]+/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

/* difficulty -> colour, so every card reads at a glance */
const LEVEL_COLOR = {
  noob: '#34d399',
  intermediate: '#7dd3fc',
  'intermediate-advanced': '#a78bfa',
  advanced: '#fbbf24',
  expert: '#f87171',
};
const levelColor = d => LEVEL_COLOR[String(d || '').toLowerCase()] || '#94a3b8';

/* One taxonomy, derived from the data itself. */
const levelsOf = scenarios => {
  const seen = new Map();
  scenarios.forEach(s => seen.set(s.difficulty, (seen.get(s.difficulty) || 0) + 1));
  const order = ['noob', 'intermediate', 'intermediate-advanced', 'advanced', 'expert'];
  return [...seen.entries()].sort((a, b) => {
    const ia = order.indexOf(a[0]), ib = order.indexOf(b[0]);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
};

function route() {
  const p = location.pathname.replace(/\/+$/, '');
  const m = p.match(/^\/swe-quiz\/scenarios\/([^/]+)(?:\/quiz)?$/);
  if (m) return p.endsWith('/quiz') ? { page: 'quiz', id: m[1] } : { page: 'detail', id: m[1] };
  const r = p.match(/^\/swe-quiz\/result\/([^/]+)$/);
  if (r) return { page: 'result', id: r[1] };
  return { page: 'list' };
}

const nav = url => { history.pushState({}, '', url); render(); };
window.addEventListener('popstate', render);

/* ---------------- list ---------------- */
function list() {
  get('/scenarios').then(({ scenarios }) => {
    const list_ = scenarios || [];
    const levels = levelsOf(list_);
    const totalQs = list_.reduce((a, s) => a + (s.question_count || 0), 0);

    app.innerHTML = `
      <section class="hero">
        <p class="kicker">LEARN BY DESIGNING</p>
        <h1>Make the call. Understand the trade&#8209;off.</h1>
        <p class="muted">Choose frontend, backend, data, infrastructure, and pattern decisions for realistic software projects.</p>
      </section>

      <div class="toolbar">
        <span class="toolbar-label">Difficulty</span>
        <button class="filter active" data-level="all">All <b>${list_.length}</b></button>
        ${levels.map(([lv, n]) =>
          `<button class="filter" data-level="${esc(lv)}">${esc(titleise(lv))} <b>${n}</b></button>`).join('')}
      </div>
      <p class="resultline" id="resultLine">${list_.length} scenarios · ${totalQs} design decisions to make</p>

      <div id="scenario-grid" class="grid"></div>`;

    const grid = document.querySelector('#scenario-grid');
    const line = document.querySelector('#resultLine');

    const draw = level => {
      document.querySelectorAll('.filter').forEach(b =>
        b.classList.toggle('active', b.dataset.level === level));
      const shown = level === 'all' ? list_ : list_.filter(s => s.difficulty === level);
      const qs = shown.reduce((a, s) => a + (s.question_count || 0), 0);
      line.textContent = level === 'all'
        ? `${list_.length} scenarios · ${totalQs} design decisions to make`
        : `${shown.length} ${titleise(level)} scenario${shown.length === 1 ? '' : 's'} · ${qs} decisions`;

      grid.innerHTML = shown.map((s, i) => `
        <a class="card" href="${root}/scenarios/${esc(s.id)}"
           style="--dc:${levelColor(s.difficulty)};animation-delay:${i * 40}ms">
          <span class="meta">${esc(titleise(s.difficulty))} · ${s.question_count} decisions</span>
          <h2>${esc(s.title)}</h2>
          <p>${esc(s.summary)}</p>
          <span class="button light">View requirements →</span>
        </a>`).join('') || '<p class="muted">No scenarios at this level.</p>';
    };

    draw('all');
    document.querySelectorAll('.filter').forEach(b => b.onclick = () => draw(b.dataset.level));
  }).catch(e => app.innerHTML = `<p class="poor">${esc(e.message)}</p>`);
}

/* ---------------- detail ---------------- */
const obj = o => Object.entries(o || {})
  .map(([k, v]) => `<b>${esc(titleise(k))}:</b> ${esc(v)}`).join('<br>');

function detail(id) {
  get(`/scenarios/${id}`).then(s => {
    const d = s.description || {};
    app.innerHTML = `
      <a class="back" href="${root}/">← All scenarios</a>
      <section class="hero detail-head">
        <p class="kicker" style="color:${levelColor(s.difficulty)}">${esc(titleise(s.difficulty))} SCENARIO</p>
        <h1>${esc(s.title)}</h1>
        <p class="muted">${esc(d.summary || s.summary || '')}</p>
      </section>

      <div class="description">
        <section><h3>Key priorities</h3>
          <ul>${(d.key_priorities || []).map(x => `<li>${esc(x)}</li>`).join('') || '<li>Not specified</li>'}</ul></section>
        <section><h3>User stories</h3>
          <ul>${(d.user_stories || []).map(x => `<li>${esc(x)}</li>`).join('') || '<li>Not specified</li>'}</ul></section>
        <section><h3>Scale &amp; performance</h3><p>${obj(d.scale_and_performance) || '—'}</p></section>
        <section><h3>Security &amp; compliance</h3><p>${obj(d.security_and_compliance) || '—'}</p></section>
      </div>

      <div class="actions">
        <a class="button" href="${root}/scenarios/${id}/quiz">Start quiz →</a>
        <a class="button light" href="${root}/">Back</a>
      </div>`;
  }).catch(e => app.innerHTML = `<p class="poor">${esc(e.message)}</p>`);
}

/* ---------------- quiz ---------------- */
function quiz(id) {
  get(`/scenarios/${id}`).then(s => {
    app.innerHTML = `
      <a class="back" href="${root}/scenarios/${id}">← ${esc(s.title)}</a>
      <section class="hero detail-head">
        <p class="kicker">QUIZ · ${(s.questions || []).length} DECISIONS</p>
        <h1>${esc(s.title)}</h1>
        <p class="muted">Choose one option for each decision, then submit. You get a rating and a justification for every call.</p>
      </section>

      <form class="quiz-form" id="quiz">
        ${(s.questions || []).map((q, i) => `
          <section class="question" style="animation-delay:${i * 55}ms">
            <span class="qnum">DECISION ${String(i + 1).padStart(2, '0')} / ${String(s.questions.length).padStart(2, '0')}</span>
            <h3>${esc(q.prompt)}</h3>
            <div class="options">
              ${q.options.map((o, oi) => `
                <label class="option">
                  <input required type="radio" name="${esc(q.id)}" value="${esc(o.id)}">
                  <span class="opt-key">${String.fromCharCode(65 + oi)}</span>
                  <span class="opt-text">${esc(o.label)}</span>
                </label>`).join('')}
            </div>
          </section>`).join('')}
        <div class="actions">
          <button class="button" type="submit">Submit answers</button>
          <a class="button light" href="${root}/scenarios/${id}">Back</a>
        </div>
      </form>`;

    document.querySelector('#quiz').onsubmit = async e => {
      e.preventDefault();
      const btn = e.target.querySelector('button[type=submit]');
      btn.disabled = true; btn.textContent = 'Scoring…';
      const selections = Object.fromEntries(new FormData(e.target));
      try {
        const r = await fetch(`${api}/scenarios/${id}/submit`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ selections }),
        });
        const result = await r.json();
        nav(`${root}/result/${result.submission_id}`);
      } catch (err) {
        btn.disabled = false; btn.textContent = 'Submit answers';
        alert(err.message);
      }
    };
  }).catch(e => app.innerHTML = `<p class="poor">${esc(e.message)}</p>`);
}

/* ---------------- result ---------------- */
function result(id) {
  get(`/submissions/${id}`).then(({ submission, scenario }) => {
    const fb = submission.feedback || {};
    const entries = Object.entries(fb);
    const good = entries.filter(([, v]) => v.rating !== 'Poor').length;
    app.innerHTML = `
      <a class="back" href="${root}/">← All scenarios</a>
      <section class="hero detail-head">
        <p class="kicker">RESULT</p>
        <h1>${esc(scenario.title)}</h1>
      </section>

      <div class="result-wrap">
        <div class="score-card">
          <div class="score">${submission.score}</div>
          <p>Your architecture decision score<br><b>${good} of ${entries.length}</b> decisions rated highly</p>
        </div>
        ${entries.map(([k, v], i) => `
          <div class="feedback" style="animation-delay:${i * 60}ms">
            <strong>${esc(titleise(k))}
              <span class="rating ${v.rating === 'Poor' ? 'poor' : 'good'}">${esc(v.rating)}</span>
            </strong>
            <p><b>You chose:</b> ${esc(v.selected_option_label)}</p>
            <p class="muted">${esc(v.justification)}</p>
          </div>`).join('')}
      </div>

      <div class="actions"><a class="button" href="${root}/">All scenarios</a></div>`;
  }).catch(e => app.innerHTML = `<p class="poor">${esc(e.message)}</p>`);
}

/* ---------------- router ---------------- */
function render() {
  const r = route();
  if (r.page === 'detail') detail(r.id);
  else if (r.page === 'quiz') quiz(r.id);
  else if (r.page === 'result') result(r.id);
  else list();
}

document.addEventListener('click', e => {
  const a = e.target.closest('a');
  if (a && a.href.startsWith(location.origin + root) && !a.target) {
    e.preventDefault();
    nav(new URL(a.href).pathname);
  }
});

render();
