/* ==========================================================================
   CloudCostLens — dashboard client
   ========================================================================== */
'use strict';

const CFG = window.__CCL__ || {};
const $ = (id) => document.getElementById(id);

/* ---------------------------------------------------------------- constants */
const PALETTE = ['#2f5bff', '#7c5cff', '#00b3c7', '#0f9d6b', '#d98317', '#dc2f43', '#5b6b8c', '#9b8cff', '#c026d3', '#0891b2'];

const ACTIONS = {
  terminate: { label: 'Terminate', color: '#dc2f43' },
  stop: { label: 'Stop', color: '#d98317' },
  delete: { label: 'Delete', color: '#dc2f43' },
  release: { label: 'Release', color: '#7c5cff' },
  keep: { label: 'Keep', color: '#0f9d6b' },
};

const GUIDANCE = {
  terminate: { tone: 'bad', title: 'Terminate this resource', steps: [
    'Confirm the instance is not required — verify owner, tags and last activity.',
    'Snapshot any data or export configuration you still need.',
    'Terminate the instance in the cloud console.',
  ] },
  stop: { tone: 'warn', title: 'Stop when idle', steps: [
    'Enable an auto-shutdown schedule for nights and weekends.',
    'Right-size the instance after observing a lighter utilization pattern.',
    'Re-evaluate in two weeks.',
  ] },
  delete: { tone: 'bad', title: 'Delete the unattached volume', steps: [
    'Confirm no snapshot or recovery plan depends on this disk.',
    'Create a final snapshot if there is any doubt.',
    'Delete the volume to stop the storage charge.',
  ] },
  release: { tone: 'violet', title: 'Release the public IP', steps: [
    'Confirm no DNS record or firewall allow-list references it.',
    'Release the IP back to the cloud pool.',
  ] },
  keep: { tone: 'good', title: 'No action needed', steps: ['Utilization looks healthy — keep monitoring.'] },
};

const ICON = {
  compute: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/></svg>',
  disk: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="16" cy="12" r="1.6"/><path d="M7 12h4"/></svg>',
  network: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18z"/></svg>',
  box: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/></svg>',
};

function kindIcon(kind) {
  const k = (kind || '').toLowerCase();
  if (['vm', 'ec2', 'instance', 'virtual machine'].includes(k)) return ICON.compute;
  if (['disk', 'ebs', 'volume', 'storage'].includes(k)) return ICON.disk;
  if (['publicip', 'eip', 'ip', 'network'].includes(k)) return ICON.network;
  return ICON.box;
}

/* ------------------------------------------------------------------ helpers */
const money = (n) => '$' + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const money0 = (n) => '$' + Number(n || 0).toLocaleString(undefined, { maximumFractionDigits: 0 });
const sum = (arr, f = (x) => x) => arr.reduce((a, b) => a + f(b), 0);
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const lastN = (arr, n) => arr.slice(Math.max(0, arr.length - n));

function periodDelta(daily, n = 7) {
  const prev = daily.slice(Math.max(0, daily.length - 2 * n), daily.length - n);
  const last = lastN(daily, n);
  if (!prev.length || !last.length) return null;
  const a = sum(prev, (d) => d.amount);
  const b = sum(last, (d) => d.amount);
  if (!a) return null;
  return ((b - a) / a) * 100;
}

function deltaChip(pct) {
  if (pct == null) return '<span class="delta flat">No prior data</span>';
  const dir = pct > 1 ? 'up' : pct < -1 ? 'down' : 'flat';
  const arrow = dir === 'up' ? '▲' : dir === 'down' ? '▼' : '▬';
  return `<span class="delta ${dir}">${arrow} ${Math.abs(pct).toFixed(1)}%</span>`;
}

/* -------------------------------------------------------------------- state */
const S = {
  costs: null, resources: [], warnings: [], days: 30, range: clamp(CFG.days || 30, 7, 30),
  view: 'overview', built: {},
  filter: { action: 'all', kind: 'all', q: '' },
  sort: { key: 'savings', dir: -1 },
  drawId: null,
};

/* ---------------------------------------------------------------- data load */
async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (res.status === 401) { window.location.href = '/login'; throw new Error('unauthorized'); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('Request failed (' + res.status + ')'));
  return data;
}

async function load(showToastOnDone) {
  const btn = $('btn-refresh'); if (btn) btn.style.opacity = '.5';
  const [costsRes, resourcesRes] = await Promise.allSettled([getJSON('/api/costs'), getJSON('/api/resources')]);
  try {
    const denied = [costsRes, resourcesRes].some((r) => r.status === 'rejected' && r.reason && r.reason.message === 'unauthorized');
    if (denied) return;

    const problems = [];
    if (costsRes.status === 'fulfilled') {
      S.costs = costsRes.value;
      S.days = costsRes.value.days || 30;
      S.range = clamp(S.range, 7, S.days);
    } else {
      problems.push('Cost data — ' + costsRes.reason.message);
    }
    if (resourcesRes.status === 'fulfilled') {
      S.resources = resourcesRes.value.resources || [];
      S.warnings = resourcesRes.value.warnings || [];
    } else {
      problems.push('Resource data — ' + resourcesRes.reason.message);
    }

    renderAll();
    if (problems.length) showError(problems.join('\n'));
    else if (S.warnings && S.warnings.length) showWarning(S.warnings);
    else $('error-banner').innerHTML = '';
    if (showToastOnDone && !problems.length) toast('Data refreshed');
  } finally { if (btn) btn.style.opacity = ''; }
}

function bannerHTML(kind, title, msg) {
  const cls = kind === 'warn' ? 'banner warn' : 'banner';
  const icon = kind === 'warn'
    ? '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0z"/>'
    : '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 2 18a2 2 0 0 0 1.7 3h16.6A2 2 0 0 0 22 18L13.7 3.9a2 2 0 0 0-3.4 0z"/>';
  return `<div class="${cls}">
       <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">${icon}</svg>
       <div><div class="b">${esc(title)}</div><div class="m">${esc(msg)}</div></div>
       <button class="btn sm" style="margin-left:auto" id="banner-retry">Retry</button>
     </div>`;
}

function showError(msg) {
  $('error-banner').innerHTML = bannerHTML('error', "Couldn't load data", msg);
  const r = $('banner-retry'); if (r) r.onclick = () => load(false);
}

function showWarning(list) {
  const preview = list.slice(0, 2).join('\n');
  const more = list.length > 2 ? `\n(+${list.length - 2} more)` : '';
  $('error-banner').innerHTML = bannerHTML('warn', 'Some data is unavailable', preview + more);
  const r = $('banner-retry'); if (r) r.onclick = () => load(false);
}

/* --------------------------------------------------------------- derivations */
function daily() { return (S.costs && S.costs.daily) || []; }
function ranged() { return lastN(daily(), S.range); }

function serviceForRange() {
  const svc = (S.costs && S.costs.by_service) || [];
  const full = sum(svc, (s) => s.amount);
  const rng = sum(ranged(), (d) => d.amount);
  const factor = full ? rng / full : 0;
  return svc.map((s) => ({ service: s.service, amount: s.amount * factor })).sort((a, b) => b.amount - a.amount);
}

function actionable() { return S.resources.filter((r) => r.recommendation.action !== 'keep'); }
function savingsTotal() { return sum(S.resources, (r) => r.recommendation.monthly_savings); }
function savingsByAction() {
  const m = {};
  actionable().forEach((r) => {
    const a = r.recommendation.action;
    m[a] = m[a] || { action: a, count: 0, savings: 0 };
    m[a].count++; m[a].savings += r.recommendation.monthly_savings;
  });
  return Object.values(m).sort((a, b) => b.savings - a.savings);
}

/* ------------------------------------------------------------------- render */
function renderAll() {
  const act = actionable();
  $('nav-res-count').textContent = S.resources.length;
  $('nav-rec-count').textContent = act.length;
  renderKpis();
  renderOverviewLists();
  renderCostView();
  renderResourceFilters();
  renderResourceTable();
  renderRecommendations();
  S.built = {};
  ensureCharts(S.view);
}

function renderKpis() {
  const d = ranged();
  const total = sum(d, (x) => x.amount);
  const n = d.length || 1;
  const avg = total / n;
  const l7 = lastN(d, 7); const avg7 = sum(l7, (x) => x.amount) / (l7.length || 1);
  const runrate = avg7 * 30;
  const delta = periodDelta(d, 7);
  const peak = d.reduce((a, b) => (b.amount > (a ? a.amount : -1) ? b : a), null);
  const save = savingsTotal();
  const act = actionable();

  const card = (opts) => `
    <div class="card kpi" ${opts.goto ? `data-goto="${opts.goto}"` : ''}>
      <div class="top">
        <span class="ic ${opts.tone}">${opts.icon}</span>
        <span class="label">${opts.label}</span>
      </div>
      <div class="value">${opts.value}</div>
      <div class="foot">${opts.foot}</div>
      ${opts.spark ? `<div class="spark"><canvas id="${opts.spark}"></canvas></div>` : ''}
    </div>`;

  $('kpis').innerHTML = [
    card({
      tone: 'blue', drag: 1, goto: 'cost', label: 'Spend · ' + S.range + 'd', value: money0(total),
      icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M2 10h20"/><circle cx="17" cy="14" r="1.2"/></svg>',
      foot: deltaChip(delta) + `<span>vs prior 7d</span>`, spark: 'spark-spend',
    }),
    card({
      tone: 'green', label: 'Daily average', value: money(avg),
      icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3 8 4-16 3 8h4"/></svg>',
      foot: peak ? `<span>Peak ${money0(peak.amount)} on ${esc(peak.date.slice(5))}</span>` : '<span>—</span>',
    }),
    card({
      tone: 'violet', label: 'Projected / month', value: money0(runrate),
      icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/></svg>',
      foot: '<span>Run-rate from last 7 days</span>',
    }),
    card({
      tone: 'amber', goto: 'recommendations', label: 'Potential savings', value: money0(save),
      icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.6.6 1 1.5 1 2.5h6c0-1 .4-1.9 1-2.5A6 6 0 0 0 12 3z"/></svg>',
      foot: `<span>${act.length} resource${act.length === 1 ? '' : 's'} to act on</span>`,
    }),
  ].join('');
}

function renderOverviewLists() {
  const top = actionable().slice().sort((a, b) => b.recommendation.monthly_savings - a.recommendation.monthly_savings).slice(0, 6);
  $('opp-list').innerHTML = top.length ? top.map((r) => `
    <div class="opp clickable" data-id="${esc(r.id)}" style="cursor:pointer">
      <div class="res-ic ${actionTone(r.recommendation.action)}">${kindIcon(r.kind)}</div>
      <div class="body">
        <div class="t">${esc(r.name)}</div>
        <div class="r">${esc(r.recommendation.reason || '')}</div>
      </div>
      <div class="save">
        <div class="v">+${money(r.recommendation.monthly_savings)}</div>
        <div class="p">/ mo</div>
      </div>
      <span class="pill ${r.recommendation.action}">${ACTIONS[r.recommendation.action] ? ACTIONS[r.recommendation.action].label : r.recommendation.action}</span>
    </div>`).join('') : emptyState('All clear', 'No idle or oversized resources detected.');
  $('opp-list').querySelectorAll('[data-id]').forEach((el) => { el.onclick = () => openDrawer(el.dataset.id); });

  const byAction = savingsByAction();
  const max = byAction.length ? byAction[0].savings : 1;
  $('action-bars').innerHTML = byAction.length ? byAction.map((g) => `
    <div class="bar-row">
      <div class="nm">${ACTIONS[g.action] ? ACTIONS[g.action].label : g.action} <span class="muted">· ${g.count}</span></div>
      <div class="amt">${money0(g.savings)}/mo</div>
      <div class="track"><div class="fill" style="width:${(g.savings / max * 100).toFixed(0)}%;background:${ACTIONS[g.action] ? ACTIONS[g.action].color : '#5b6b8c'}"></div></div>
    </div>`).join('') : '<div class="empty"><div class="t">Nothing to optimize</div><div class="s">Savings opportunities will appear here.</div></div>';
}

function actionTone(a) {
  if (a === 'terminate' || a === 'delete') return 'red';
  if (a === 'stop') return 'amber';
  if (a === 'release') return 'violet';
  return 'green';
}

function renderCostView() {
  const d = ranged();
  const total = sum(d, (x) => x.amount);
  const n = d.length || 1;
  const avg = total / n;
  const peak = d.reduce((a, b) => (b.amount > (a ? a.amount : -1) ? b : a), null);
  const low = d.reduce((a, b) => (a == null || b.amount < a.amount ? b : a), null);
  $('cost-stats').innerHTML = [
    ['Period spend', money(total)],
    ['Daily average', money(avg)],
    ['Peak day', peak ? `${money0(peak.amount)}` : '—'],
    ['Lowest day', low ? `${money0(low.amount)}` : '—'],
  ].map(([l, v]) => `<div class="stat"><div class="l">${l}</div><div class="v">${v}</div></div>`).join('');
  $('svc-sub').textContent = `Last ${S.range} days · proportional mix`;
  $('trend-sub').textContent = `Cost per day · last ${S.range} days`;

  const svc = serviceForRange();
  const svcTotal = sum(svc, (s) => s.amount) || 1;
  $('service-bars').innerHTML = svc.map((s, i) => `
    <div class="bar-row">
      <div class="nm">${esc(s.service)}</div>
      <div class="amt">${money(s.amount)} <span class="muted">${(s.amount / svcTotal * 100).toFixed(0)}%</span></div>
      <div class="track"><div class="fill" style="width:${(s.amount / svcTotal * 100).toFixed(1)}%;background:${PALETTE[i % PALETTE.length]}"></div></div>
    </div>`).join('') || emptyState('No cost data', 'No services reported for this period.');

  $('service-legend').innerHTML = svc.slice(0, 6).map((s, i) => `
    <div class="row">
      <span class="sw" style="background:${PALETTE[i % PALETTE.length]}"></span>
      <span class="nm">${esc(s.service)}</span>
      <span class="amt">${money(s.amount)}</span>
      <span class="pc">${(s.amount / svcTotal * 100).toFixed(0)}%</span>
    </div>`).join('');
  $('donut-total').textContent = money0(total);

  const save = savingsTotal();
  const act = actionable();
  const runrate = (sum(lastN(d, 7), (x) => x.amount) / (lastN(d, 7).length || 1)) * 30;
  const topSvc = svc[0];
  const drivers = [];
  if (topSvc) drivers.push(`<b>${esc(topSvc.service)}</b> is the largest cost driver at ${(topSvc.amount / svcTotal * 100).toFixed(0)}% of spend.`);
  if (act.length) drivers.push(`Remediating <b>${act.length}</b> resource${act.length === 1 ? '' : 's'} would cut about <b>${money0(save)}/mo</b>${runrate ? ` (${(save / runrate * 100).toFixed(0)}% of run-rate)` : ''}.`);
  const pd = periodDelta(d, 7);
  if (pd != null) drivers.push(`Spend is ${pd >= 0 ? 'trending up' : 'trending down'} <b>${Math.abs(pd).toFixed(1)}%</b> versus the prior week.`);
  $('cost-drivers').innerHTML = drivers.length
    ? drivers.map((t, i) => `<div class="callout ${['', 'good', ''][i % 3]}" style="margin-bottom:10px"><p>${t}</p></div>`).join('')
    : emptyState('No insights', 'Not enough data to surface drivers yet.');
}

/* ------------------------------------------------------------------- charts */
function ensureCharts(view) {
  if (!S.costs || S.built[view]) return;
  S.built[view] = true;
  const d = ranged();
  if (view === 'overview') { buildDaily('chart-daily'); buildService('chart-service'); buildSpark('spark-spend', d); }
  if (view === 'cost') { buildDaily('chart-daily-2'); }
}

function destroy(id) { if (S.charts && S.charts[id]) { S.charts[id].destroy(); delete S.charts[id]; } }
S.charts = {};

function makeCanvasChart(id, config) {
  const el = $(id); if (!el) return;
  destroy(id);
  S.charts[id] = new Chart(el.getContext('2d'), config);
}

function buildDaily(id) {
  const d = ranged();
  makeCanvasChart(id, {
    type: 'line',
    data: {
      labels: d.map((x) => x.date.slice(5)),
      datasets: [{
        data: d.map((x) => x.amount),
        borderColor: '#2f5bff', borderWidth: 2, tension: 0.35, fill: true,
        pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: '#2f5bff',
        pointHoverBorderColor: '#fff', pointHoverBorderWidth: 2,
        backgroundColor: (c) => {
          const { ctx, chartArea } = c.chart;
          if (!chartArea) return 'rgba(47,91,255,.12)';
          const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
          g.addColorStop(0, 'rgba(47,91,255,.26)'); g.addColorStop(1, 'rgba(47,91,255,0)');
          return g;
        },
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: { backgroundColor: '#0f172a', padding: 10, cornerRadius: 8, displayColors: false, titleFont: { family: 'Inter' }, bodyFont: { family: 'Inter' },
          callbacks: { label: (it) => money(it.parsed.y) } },
      },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { color: '#7b879b', maxTicksLimit: 8, font: { size: 11, family: 'Inter' } } },
        y: { beginAtZero: true, grid: { color: '#eef1f6' }, border: { display: false }, ticks: { color: '#7b879b', font: { size: 11, family: 'Inter' }, callback: (v) => '$' + v } },
      },
    },
  });
}

function buildService(id) {
  const svc = serviceForRange();
  makeCanvasChart(id, {
    type: 'doughnut',
    data: { labels: svc.map((s) => s.service), datasets: [{ data: svc.map((s) => s.amount), backgroundColor: svc.map((_, i) => PALETTE[i % PALETTE.length]), borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: { legend: { display: false }, tooltip: { backgroundColor: '#0f172a', padding: 10, cornerRadius: 8, callbacks: { label: (it) => `${it.label}: ${money(it.parsed)}` } } },
    },
  });
}

function buildSpark(id, d) {
  makeCanvasChart(id, {
    type: 'line',
    data: { labels: d.map((x) => x.date), datasets: [{ data: d.map((x) => x.amount), borderColor: '#2f5bff', borderWidth: 1.6, tension: 0.4, fill: true, pointRadius: 0, backgroundColor: 'rgba(47,91,255,.10)' }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } }, elements: { line: { borderJoinStyle: 'round' } } },
  });
}

/* ---------------------------------------------------------------- resources */
function renderResourceFilters() {
  const kinds = Array.from(new Set(S.resources.map((r) => r.kind))).sort();
  $('res-kind').innerHTML = '<option value="all">All types</option>' + kinds.map((k) => `<option value="${esc(k)}">${esc(k)}</option>`).join('');

  const counts = { all: S.resources.length };
  S.resources.forEach((r) => { counts[r.recommendation.action] = (counts[r.recommendation.action] || 0) + 1; });
  const order = ['all', 'terminate', 'stop', 'delete', 'release', 'keep'];
  $('res-chips').innerHTML = order.filter((a) => counts[a]).map((a) => {
    const label = a === 'all' ? 'All' : (ACTIONS[a] ? ACTIONS[a].label : a);
    return `<button class="chip ${S.filter.action === a ? 'active' : ''}" data-action="${a}">${label}<span class="n">${counts[a]}</span></button>`;
  }).join('');

  $('res-chips').querySelectorAll('.chip').forEach((c) => {
    c.onclick = () => { S.filter.action = c.dataset.action; renderResourceFilters(); renderResourceTable(); };
  });
}

function filteredResources() {
  let list = S.resources.slice();
  if (S.filter.action !== 'all') list = list.filter((r) => r.recommendation.action === S.filter.action);
  if (S.filter.kind !== 'all') list = list.filter((r) => r.kind === S.filter.kind);
  const q = S.filter.q.trim().toLowerCase();
  if (q) list = list.filter((r) => `${r.name} ${r.kind} ${r.state} ${r.detail}`.toLowerCase().includes(q));
  const { key, dir } = S.sort;
  const val = (r) => {
    if (key === 'name') return r.name.toLowerCase();
    if (key === 'kind') return r.kind.toLowerCase();
    if (key === 'cost') return r.monthly_cost;
    if (key === 'cpu') return r.cpu == null ? -1 : r.cpu;
    if (key === 'action') return r.recommendation.action;
    if (key === 'state') return r.state;
    return r.recommendation.monthly_savings;
  };
  list.sort((a, b) => { const x = val(a), y = val(b); return (x < y ? -1 : x > y ? 1 : 0) * dir; });
  return list;
}

function cpuCell(cpu) {
  if (cpu == null) return '<div class="cpu"><span class="na">—</span></div>';
  const color = cpu < 1 ? '#dc2f43' : cpu < 5 ? '#d98317' : cpu < 60 ? '#0f9d6b' : '#2f5bff';
  return `<div class="cpu"><span class="track"><span class="fill" style="width:${clamp(cpu, 0, 100)}%;background:${color}"></span></span><span class="val">${cpu}%</span></div>`;
}

function renderResourceTable() {
  const list = filteredResources();
  const body = $('res-body');
  if (!list.length) {
    body.innerHTML = `<tr><td colspan="7">${emptyState('No resources match', 'Adjust the filters or search to see more.')}</td></tr>`;
    return;
  }
  body.innerHTML = list.map((r) => {
    const rec = r.recommendation;
    return `<tr class="clickable" data-id="${esc(r.id)}">
      <td><div class="res-name"><span class="res-ic ${actionTone(rec.action)}">${kindIcon(r.kind)}</span>
        <span><span class="t">${esc(r.name)}</span><div class="s">${esc(r.detail)}</div></span></div></td>
      <td><span class="muted">${esc(r.kind)}</span></td>
      <td><span class="state ${esc(r.state)}">${esc(r.state)}</span></td>
      <td class="num">${cpuCell(r.cpu)}</td>
      <td class="num"><span class="money">${money(r.monthly_cost)}</span></td>
      <td><span class="pill ${rec.action}">${ACTIONS[rec.action] ? ACTIONS[rec.action].label : rec.action}</span></td>
      <td class="num"><span class="money ${rec.monthly_savings > 0 ? 'save' : ''}">${rec.monthly_savings > 0 ? '+' + money(rec.monthly_savings) : '—'}</span></td>
    </tr>`;
  }).join('');
  body.querySelectorAll('tr.clickable').forEach((tr) => { tr.onclick = () => openDrawer(tr.dataset.id); });

  document.querySelectorAll('thead th[data-key]').forEach((th) => {
    th.classList.toggle('sorted', th.dataset.key === S.sort.key);
    const mark = th.querySelector('.arw');
    if (mark && th.dataset.key === S.sort.key) mark.textContent = S.sort.dir === 1 ? '▲' : '▼';
  });
}

/* ------------------------------------------------------------ recommendations */
function renderRecommendations() {
  const byAction = savingsByAction();
  $('rec-cards').innerHTML = byAction.length ? byAction.map((g) => `
    <div class="card rec-card ${g.action}">
      <div class="card-head" style="margin-bottom:8px"><span class="pill ${g.action}">${ACTIONS[g.action] ? ACTIONS[g.action].label : g.action}</span></div>
      <div class="big">${money0(g.savings)}<span class="muted" style="font-size:13px;font-weight:600">/mo</span></div>
      <div class="cap">${g.count} resource${g.count === 1 ? '' : 's'} · save up to ${money0(g.savings * 12)}/yr</div>
    </div>`).join('') : `<div class="card" style="grid-column:1/-1">${emptyState('Everything looks optimized', 'No wasteful resources detected in this scope.')}</div>`;

  const list = actionable().slice().sort((a, b) => b.recommendation.monthly_savings - a.recommendation.monthly_savings);
  $('rec-list').innerHTML = list.length ? list.map((r) => `
    <div class="opp cd" data-id="${esc(r.id)}" style="cursor:pointer">
      <div class="res-ic ${actionTone(r.recommendation.action)}">${kindIcon(r.kind)}</div>
      <div class="body">
        <div class="t">${esc(r.name)} <span class="muted" style="font-weight:500">· ${esc(r.kind)} · ${esc(r.detail)}</span></div>
        <div class="r">${esc(r.recommendation.reason || '')}</div>
      </div>
      <span class="pill ${r.recommendation.action}">${ACTIONS[r.recommendation.action] ? ACTIONS[r.recommendation.action].label : r.recommendation.action}</span>
      <div class="save"><div class="v">+${money(r.recommendation.monthly_savings)}</div><div class="p">/ mo</div></div>
    </div>`).join('') : emptyState('No recommendations', 'Nothing needs attention right now.');
  $('rec-list').querySelectorAll('.cd').forEach((el) => { el.onclick = () => openDrawer(el.dataset.id); });
}

/* ------------------------------------------------------------------- drawer */
function openDrawer(id) {
  const r = S.resources.find((x) => String(x.id) === String(id));
  if (!r) return;
  S.drawId = id;
  const rec = r.recommendation;
  const g = GUIDANCE[rec.action] || GUIDANCE.keep;
  $('drawer-title').textContent = r.name;
  $('drawer-sub').textContent = `${r.kind} · ${r.state}`;
  $('drawer-body').innerHTML = `
    <div class="kv">
      <div class="k">Resource ID</div><div class="v">${esc(r.id)}</div>
      <div class="k">Type</div><div class="v">${esc(r.kind)}</div>
      <div class="k">State</div><div class="v"><span class="state ${esc(r.state)}">${esc(r.state)}</span></div>
      <div class="k">Details</div><div class="v">${esc(r.detail)}</div>
      <div class="k">CPU average</div><div class="v">${r.cpu == null ? 'Not available' : r.cpu + '%'}</div>
      <div class="k">Monthly cost</div><div class="v">${money(r.monthly_cost)}</div>
      <div class="k">Potential savings</div><div class="v" style="color:var(--good)">${money(rec.monthly_savings)}/mo · ${money(rec.monthly_savings * 12)}/yr</div>
    </div>
    <div class="callout ${g.tone}">
      <h4>${ACTIONS[rec.action] ? ACTIONS[rec.action].label : rec.action} · ${esc(g.title)}</h4>
      <p>${esc(rec.reason || '')}</p>
      <ol class="steps">${g.steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ol>
    </div>
    <p class="muted" style="font-size:12px;margin-top:14px">CloudCostLens is read-only. Review and apply changes in your cloud console.</p>`;
  $('drawer').classList.add('open');
  $('drawer').setAttribute('aria-hidden', 'false');
  $('scrim').classList.add('open');
}
function closeDrawer() {
  $('drawer').classList.remove('open');
  $('drawer').setAttribute('aria-hidden', 'true');
  $('scrim').classList.remove('open');
}

/* --------------------------------------------------------------------- misc */
function emptyState(t, s) {
  return `<div class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="9"/><path d="M8 13s1.5 2 4 2 4-2 4-2"/><path d="M9 9h.01M15 9h.01"/></svg><div class="t">${esc(t)}</div><div class="s">${esc(s)}</div></div>`;
}

function toast(msg) {
  const el = document.createElement('div');
  el.className = 'toast';
  el.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg>${esc(msg)}`;
  $('toasts').appendChild(el);
  setTimeout(() => { el.style.transition = 'opacity .3s'; el.style.opacity = '0'; setTimeout(() => el.remove(), 300); }, 2200);
}

function exportCsv() {
  const rows = [['Name', 'Type', 'State', 'Detail', 'CPU', 'MonthlyCost', 'Action', 'Reason', 'MonthlySavings']];
  filteredResources().forEach((r) => rows.push([r.name, r.kind, r.state, r.detail, r.cpu == null ? '' : r.cpu, r.monthly_cost, r.recommendation.action, r.recommendation.reason, r.recommendation.monthly_savings]));
  const csv = rows.map((row) => row.map((c) => `"${String(c == null ? '' : c).replace(/"/g, '""')}"`).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const a = document.createElement('a');
  a.href = url; a.download = 'cloudcostlens-resources.csv'; a.click();
  URL.revokeObjectURL(url); toast('Exported resources to CSV');
}

/* ------------------------------------------------------------------ routing */
function activateView(v) {
  if (!['overview', 'cost', 'resources', 'recommendations'].includes(v)) v = 'overview';
  S.view = v;
  document.querySelectorAll('.view').forEach((el) => el.classList.toggle('active', el.id === 'view-' + v));
  document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('active', a.dataset.view === v));
  $('view-title').textContent = { overview: 'Overview', cost: 'Cost Analysis', resources: 'Resources', recommendations: 'Recommendations' }[v];
  $('sidebar').classList.remove('open');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  ensureCharts(v);
}

/* -------------------------------------------------------------------- wire */
function wire() {
  document.querySelectorAll('#nav a').forEach((a) => {
    a.onclick = (e) => { e.preventDefault(); history.replaceState(null, '', '#' + a.dataset.view); activateView(a.dataset.view); };
  });
  document.querySelectorAll('[data-goto]').forEach((b) => {
    b.onclick = () => { history.replaceState(null, '', '#' + b.dataset.goto); activateView(b.dataset.goto); };
  });
  document.body.addEventListener('click', (e) => {
    const k = e.target.closest('.kpi[data-goto]');
    if (k) { history.replaceState(null, '', '#' + k.dataset.goto); activateView(k.dataset.goto); }
  });

  $('range-seg').querySelectorAll('button').forEach((b) => {
    b.onclick = () => {
      S.range = clamp(parseInt(b.dataset.days, 10), 7, S.days);
      $('range-seg').querySelectorAll('button').forEach((x) => x.classList.toggle('active', x === b));
      renderKpis(); renderOverviewLists(); renderCostView();
      S.built = {}; ensureCharts(S.view);
    };
  });

  $('res-search').oninput = (e) => { S.filter.q = e.target.value; renderResourceTable(); };
  $('res-kind').onchange = (e) => { S.filter.kind = e.target.value; renderResourceTable(); };
  $('res-sort').onchange = (e) => {
    const map = { savings: 'savings', cost: 'cost', cpu: 'cpu', name: 'name' };
    S.sort = { key: map[e.target.value] || 'savings', dir: e.target.value === 'name' ? 1 : -1 };
    renderResourceTable();
  };
  document.querySelectorAll('thead th[data-key]').forEach((th) => {
    th.onclick = () => {
      if (th.classList.contains('no-sort')) return;
      const key = th.dataset.key === 'cost' ? 'cost' : th.dataset.key;
      if (S.sort.key === key) S.sort.dir *= -1; else S.sort = { key, dir: key === 'name' ? 1 : -1 };
      renderResourceTable();
    };
  });

  $('btn-refresh').onclick = () => load(true);
  $('btn-export').onclick = exportCsv;
  $('drawer-close').onclick = closeDrawer;
  $('scrim').onclick = closeDrawer;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
  $('hamburger').onclick = () => $('sidebar').classList.toggle('open');
  $('btn-signout').onclick = async () => { await fetch('/api/auth/logout', { method: 'POST' }); window.location.href = '/login'; };

  // set the range segment to the available window
  const seg = $('range-seg').querySelectorAll('button');
  seg.forEach((b) => {
    const d = parseInt(b.dataset.days, 10);
    b.disabled = d > S.days;
    b.classList.toggle('active', d === S.range);
  });
}

/* --------------------------------------------------------------------- init */
wire();
const initial = (location.hash || '#overview').slice(1);
activateView(initial);
load(false);
