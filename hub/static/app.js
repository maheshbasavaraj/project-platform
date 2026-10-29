const icons = {"game-forge":"✧", dsds:"⌘", "swe-quiz":"◈"};
const el = document.querySelector('#projects');
const esc = (v) => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function load() {
  try {
    const {projects} = await fetch('/api/projects').then(r => r.json());
    el.innerHTML = projects.map((p, i) => `
      <a class="card ${esc(p.color)}" href="${esc(p.url)}">
        <div class="card-top"><span class="number">0${i+1}</span><span class="arrow">↗</span></div>
        <div class="icon">${icons[p.id] || '✦'}</div>
        <p class="eyebrow">${esc(p.eyebrow)}</p>
        <h2>${esc(p.title)}</h2>
        <p>${esc(p.description)}</p>
        <div class="tags">${p.topics.map(t => `<span class="tag">${esc(t)}</span>`).join('')}</div>
        <span class="open">Open space →</span>
      </a>`).join('');
  } catch (e) { el.innerHTML = '<p class="loading">Could not load the learning spaces.</p>'; }
}
load();
