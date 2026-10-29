/* Game Forge front-end */
const $ = (s, r = document) => r.querySelector(s);
const games = $('#games');
const form = $('#forge-form');
const result = $('#result');

const esc = v => String(v ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// pretty size, so a 16574-byte game reads as "16.2 KB"
const kb = n => (n == null ? '' : n >= 1024 ? (n / 1024).toFixed(1) + ' KB' : n + ' B');

const payload = () => {
  const f = new FormData(form);
  return {
    topic: f.get('topic'),
    audience: f.get('audience'),
    session_minutes: Number(f.get('session_minutes')),
    checklist: f.get('checklist') === 'on',
  };
};

const show = data => {
  result.hidden = false;
  result.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
};

const call = (path, body) => fetch(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
}).then(async r => {
  const d = await r.json();
  if (!r.ok) throw Error(d.detail || d.message || 'Request failed');
  return d;
});

const busy = (btn, on) => {
  btn.disabled = on;
  btn.classList.toggle('busy', on);
  if (on) btn.dataset.label = btn.textContent;
};

/* keep the number input and the slider in sync */
const mins = $('[name=session_minutes]');
const slider = $('#mins');
if (mins && slider) {
  slider.addEventListener('input', () => { mins.value = slider.value; });
  mins.addEventListener('input', () => { slider.value = mins.value; });
}

$('#preview').onclick = async () => {
  const btn = $('#preview');
  busy(btn, true);
  try { show(await call('/game-forge/api/prompt', payload())); }
  catch (e) { show({ error: e.message }); }
  finally { busy(btn, false); }
};

form.onsubmit = async e => {
  e.preventDefault();
  const btn = form.querySelector('button[type=submit]');
  busy(btn, true);
  show({ status: 'Generating through Game MCP and Ollama…', topic: payload().topic });
  try {
    const d = await call('/game-forge/api/generate', payload());
    show(d);
    load();
  } catch (err) {
    show({ error: err.message });
  } finally {
    busy(btn, false);
  }
};

function load() {
  fetch('/game-forge/api/games')
    .then(r => r.json())
    .then(({ games: items }) => {
      const list = items || [];
      const cnt = $('#gameCount');
      if (cnt) cnt.textContent = list.length + (list.length === 1 ? ' game' : ' games');
      games.innerHTML = list.map((g, i) => `
        <a class="card" href="/game-forge${g.url.replace('/game-forge', '')}"
           style="animation-delay:${i * 45}ms">
          <span class="sprites"><i></i><i></i><i></i></span>
          <b>Play now ↗</b>
          <h2>${esc((g.name || g.title || '').replace(/[-_]/g, ' '))}</h2>
          <p>Saved through the Game Forge MCP pipeline.</p>
          ${g.bytes != null ? `<span class="bytes">${esc(kb(g.bytes))}</span>` : ''}
        </a>`).join('') || '<p class="loading">No games are available yet — forge the first one above.</p>';
    })
    .catch(() => { games.innerHTML = '<p class="loading">Games could not be loaded.</p>'; });
}

/* MCP tool chips */
fetch('/game-forge/api/mcp/tools')
  .then(r => r.json())
  .then(d => {
    const tools = d.tools || d;
    const list = Array.isArray(tools) ? tools : Object.keys(tools || {});
    if (!list.length) return;
    $('#toolRow').innerHTML = list.map((t, i) => {
      const name = typeof t === 'string' ? t : (t.name || '');
      return `<span class="tool-chip" style="animation-delay:${i * 60}ms">${esc(name)}()</span>`;
    }).join('');
  })
  .catch(() => {
    $('#toolRow').innerHTML =
      ['build_game_prompt', 'save_game', 'review_checklist', 'list_games']
        .map((n, i) => `<span class="tool-chip" style="animation-delay:${i * 60}ms">${n}()</span>`).join('');
  });

load();
