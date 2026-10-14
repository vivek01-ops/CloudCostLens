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
  diag: null,
};

/* ---------------------------------------------------------------- data load */
let throttleTimer = null;
function clearThrottle() { if (throttleTimer) { clearInterval(throttleTimer); throttleTimer = null; } }

async function getJSON(url) {
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (res.status === 401) { window.location.href = '/login'; throw new Error('unauthorized'); }
  const data = await res.json().catch(() => ({}));
  if (res.status === 429) {
    const err = new Error(data.error || 'The cloud provider is throttling requests. Please wait a moment.');
    err.throttled = true;
    err.retryAfter = Number(res.headers.get('Retry-After')) || Number(data.retry_after) || 15;
    throw err;
  }
  if (!res.ok) throw new Error(data.error || ('Request failed (' + res.status + ')'));
  return data;
}

async function load(showToastOnDone, force) {
  clearThrottle();
  const btn = $('btn-refresh'); if (btn) { btn.classList.add('spinning'); btn.setAttribute('aria-busy', 'true'); }
  const main = $('main'); if (main) main.setAttribute('aria-busy', 'true');
  renderSkeletons();
  const q = force ? '?force=1' : '';
  const [costsRes, resourcesRes] = await Promise.allSettled([getJSON('/api/costs' + q), getJSON('/api/resources' + q)]);
  try {
    const denied = [costsRes, resourcesRes].some((r) => r.status === 'rejected' && r.reason && r.reason.message === 'unauthorized');
    if (denied) return;

    const problems = [];
    let throttleWait = 0;
    if (costsRes.status === 'fulfilled') {
      S.costs = costsRes.value;
      S.days = costsRes.value.days || 30;
      S.range = clamp(S.range, 7, S.days);
    } else {
      problems.push('Cost data — ' + costsRes.reason.message);
      if (costsRes.reason && costsRes.reason.throttled) throttleWait = Math.max(throttleWait, costsRes.reason.retryAfter);
    }
    if (resourcesRes.status === 'fulfilled') {
      S.resources = resourcesRes.value.resources || [];
      S.warnings = resourcesRes.value.warnings || [];
    } else {
      problems.push('Resource data — ' + resourcesRes.reason.message);
      if (resourcesRes.reason && resourcesRes.reason.throttled) throttleWait = Math.max(throttleWait, resourcesRes.reason.retryAfter);
    }

    renderAll();
    if (throttleWait) showThrottled(throttleWait);
    else if (problems.length) showError(problems.join('\n'));
    else if (S.warnings && S.warnings.length) showWarning(S.warnings);
    else $('error-banner').innerHTML = '';
    if (showToastOnDone && !problems.length) toast('Data refreshed');
  } finally {
    if (btn) { btn.classList.remove('spinning'); btn.removeAttribute('aria-busy'); }
    if (main) main.removeAttribute('aria-busy');
  }
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

function showThrottled(seconds) {
  const end = Date.now() + seconds * 1000;
  const tick = () => {
    const left = Math.max(0, Math.ceil((end - Date.now()) / 1000));
    $('error-banner').innerHTML = bannerHTML(
      'warn', 'Cloud provider is busy',
      left > 0 ? `Too many requests were sent to the cloud API. Retrying automatically in ${left}s…`
               : 'Retrying now…'
    );
    const r = $('banner-retry'); if (r) r.onclick = () => load(false);
    if (left <= 0) { clearThrottle(); load(false); }
  };
  clearThrottle();
  tick();
  throttleTimer = setInterval(tick, 1000);
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

/* ----------------------------------------------------------------- skeletons */
function skelRows(n) {
  return Array.from({ length: n }).map(() => `
    <div class="skel-row">
      <span class="skeleton" style="width:36px;height:36px;border-radius:9px;flex:0 0 auto"></span>
      <div style="flex:1;min-width:0">
        <span class="skeleton" style="width:45%;height:12px;display:block;margin-bottom:7px"></span>
        <span class="skeleton" style="width:70%;height:10px;display:block"></span>
      </div>
      <span class="skeleton" style="width:64px;height:22px;border-radius:999px;flex:0 0 auto"></span>
    </div>`).join('');
}

function skelBars(n) {
  return Array.from({ length: n }).map(() => `
    <div class="skel-bar">
      <span class="skeleton" style="width:34%;height:11px;display:block"></span>
      <span class="skeleton" style="width:100%;height:8px;border-radius:999px;display:block;margin:9px 0 4px"></span>
    </div>`).join('');
}

function skelTableRows(n, cols) {
  return Array.from({ length: n }).map(() => `<tr>${Array.from({ length: cols }).map(() =>
    '<td><span class="skeleton" style="height:14px;display:block"></span></td>').join('')}</tr>`).join('');
}

function skelOverlay(id) {
  const el = $(id);
  const parent = el && el.parentElement;
  if (!parent || parent.querySelector('.skel-overlay')) return;
  const o = document.createElement('div');
  o.className = 'skel-overlay skeleton';
  parent.appendChild(o);
}

function renderSkeletons() {
  const kpis = $('kpis');
  if (kpis) kpis.innerHTML = Array.from({ length: 4 }).map(() => `
    <div class="card kpi">
      <div class="top"><span class="skeleton" style="width:30px;height:30px;border-radius:8px"></span><span class="skeleton" style="width:92px;height:12px"></span></div>
      <span class="skeleton" style="width:130px;height:26px;display:block;margin:14px 0 10px"></span>
      <span class="skeleton" style="width:112px;height:12px;display:block"></span>
    </div>`).join('');

  const opp = $('opp-list'); if (opp) opp.innerHTML = skelRows(4);
  const bars = $('action-bars'); if (bars) bars.innerHTML = skelBars(3);
  const stats = $('cost-stats');
  if (stats) stats.innerHTML = Array.from({ length: 4 }).map(() => `
    <div class="stat">
      <span class="skeleton" style="width:70%;height:11px;display:block;margin-bottom:9px"></span>
      <span class="skeleton" style="width:52%;height:22px;display:block"></span>
    </div>`).join('');
  const svcBars = $('service-bars'); if (svcBars) svcBars.innerHTML = skelBars(5);
  const legend = $('service-legend');
  if (legend) legend.innerHTML = Array.from({ length: 5 }).map(() => `
    <div class="row">
      <span class="skeleton" style="width:11px;height:11px;border-radius:3px;flex:0 0 auto"></span>
      <span class="skeleton" style="flex:1;height:11px"></span>
      <span class="skeleton" style="width:56px;height:11px"></span>
    </div>`).join('');
  const drivers = $('cost-drivers'); if (drivers) drivers.innerHTML = skelRows(3);
  const resBody = $('res-body'); if (resBody) resBody.innerHTML = skelTableRows(6, 7);
  const chips = $('res-chips');
  if (chips) chips.innerHTML = Array.from({ length: 5 }).map(() =>
    '<span class="skeleton" style="width:84px;height:30px;border-radius:999px;display:inline-block"></span>').join('');
  const recCards = $('rec-cards');
  if (recCards) recCards.innerHTML = Array.from({ length: 4 }).map(() => `
    <div class="card">
      <span class="skeleton" style="width:64px;height:22px;border-radius:999px;display:block;margin-bottom:14px"></span>
      <span class="skeleton" style="width:112px;height:30px;display:block;margin-bottom:12px"></span>
      <span class="skeleton" style="width:80%;height:11px;display:block"></span>
    </div>`).join('');
  const recList = $('rec-list'); if (recList) recList.innerHTML = skelRows(4);

  ['chart-daily', 'chart-service', 'chart-daily-2'].forEach(skelOverlay);
}

function clearSkeletons() {
  document.querySelectorAll('.skel-overlay').forEach((o) => o.remove());
}

/* ------------------------------------------------------------------- render */
function renderAll() {
  clearSkeletons();
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

function cssVar(name) {
  if (typeof getComputedStyle !== 'function' || !document.documentElement) return '';
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function makeCanvasChart(id, config, label) {
  const el = $(id); if (!el) return;
  destroy(id);
  el.setAttribute('role', 'img');
  el.setAttribute('aria-label', label || 'Chart');
  S.charts[id] = new Chart(el.getContext('2d'), config);
}

function buildDaily(id) {
  const d = ranged();
  const primary = cssVar('--primary') || '#2f5bff';
  const muted = cssVar('--muted') || '#7b879b';
  const grid = cssVar('--border') || '#eef1f6';
  const tip = cssVar('--sidebar') || '#0f172a';
  makeCanvasChart(id, {
    type: 'line',
    data: {
      labels: d.map((x) => x.date.slice(5)),
      datasets: [{
        data: d.map((x) => x.amount),
        borderColor: primary, borderWidth: 2, tension: 0.35, fill: true,
        pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: primary,
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
        tooltip: { backgroundColor: tip, padding: 10, cornerRadius: 8, displayColors: false, titleFont: { family: 'Inter' }, bodyFont: { family: 'Inter' },
          callbacks: { label: (it) => money(it.parsed.y) } },
      },
      scales: {
        x: { grid: { display: false }, border: { display: false }, ticks: { color: muted, maxTicksLimit: 8, font: { size: 11, family: 'Inter' } } },
        y: { beginAtZero: true, grid: { color: grid }, border: { display: false }, ticks: { color: muted, font: { size: 11, family: 'Inter' }, callback: (v) => '$' + v } },
      },
    },
  }, 'Daily spend trend');
}

function buildService(id) {
  const svc = serviceForRange();
  const tip = cssVar('--sidebar') || '#0f172a';
  makeCanvasChart(id, {
    type: 'doughnut',
    data: { labels: svc.map((s) => s.service), datasets: [{ data: svc.map((s) => s.amount), backgroundColor: svc.map((_, i) => PALETTE[i % PALETTE.length]), borderWidth: 0, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '68%',
      plugins: { legend: { display: false }, tooltip: { backgroundColor: tip, padding: 10, cornerRadius: 8, callbacks: { label: (it) => `${it.label}: ${money(it.parsed)}` } } },
    },
  }, 'Spend by service');
}

function buildSpark(id, d) {
  const primary = cssVar('--primary') || '#2f5bff';
  makeCanvasChart(id, {
    type: 'line',
    data: { labels: d.map((x) => x.date), datasets: [{ data: d.map((x) => x.amount), borderColor: primary, borderWidth: 1.6, tension: 0.4, fill: true, pointRadius: 0, backgroundColor: 'rgba(47,91,255,.10)' }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } }, elements: { line: { borderJoinStyle: 'round' } } },
  }, 'Spend trend sparkline');
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
  const el = $('drawer');
  S.lastFocus = document.activeElement;
  el.inert = false;
  el.classList.add('open');
  el.setAttribute('aria-hidden', 'false');
  el.setAttribute('role', 'dialog');
  el.setAttribute('aria-modal', 'true');
  el.setAttribute('aria-labelledby', 'drawer-title');
  el.tabIndex = -1;
  $('scrim').classList.add('open');
  const close = $('drawer-close');
  if (close) close.focus();
}
function closeDrawer() {
  const el = $('drawer');
  if (!el.classList.contains('open')) return;
  el.classList.remove('open');
  el.setAttribute('aria-hidden', 'true');
  el.removeAttribute('aria-modal');
  el.removeAttribute('tabIndex');
  el.inert = true;
  $('scrim').classList.remove('open');
  if (S.lastFocus && typeof S.lastFocus.focus === 'function') S.lastFocus.focus();
}

function drawerKeydown(e) {
  const el = $('drawer');
  if (!el.classList.contains('open')) return;
  if (e.key === 'Escape') { e.preventDefault(); closeDrawer(); return; }
  if (e.key !== 'Tab') return;
  const nodes = el.querySelectorAll('a[href], button:not([disabled]), input, select, textarea, [tabindex]:not([tabindex="-1"])');
  const list = Array.prototype.filter.call(nodes, (n) => n.offsetParent !== null);
  if (!list.length) return;
  const first = list[0], last = list[list.length - 1];
  if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
  else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
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

/* -------------------------------------------------------------- diagnostics */
const DIAG_OK = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>';
const DIAG_BAD = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 6l12 12M18 6L6 18"/></svg>';

function providerLabel(p) {
  return { aws: 'Amazon Web Services', azure: 'Microsoft Azure', demo: 'Demo sandbox' }[p] || p;
}

async function loadDiagnostics(force) {
  const body = $('diag-body');
  if (!body) return;
  if (S.diag && !force) { renderDiagnostics(); return; }
  const rbtn = $('btn-diag-refresh'); if (rbtn) { rbtn.classList.add('spinning'); rbtn.setAttribute('aria-busy', 'true'); }
  body.setAttribute('aria-busy', 'true');
  body.innerHTML = `
    <div class="grid g-2">
      <div class="card"><div class="card-head"><span class="skeleton" style="width:110px;height:16px"></span></div>${skelRows(6)}</div>
      <div class="card"><div class="card-head"><span class="skeleton" style="width:90px;height:16px"></span></div>${skelRows(4)}</div>
    </div>
    <div class="grid g-2" style="margin-top:16px">
      <div class="card"><div class="card-head"><span class="skeleton" style="width:160px;height:16px"></span></div>${skelRows(2)}</div>
      <div class="card"><div class="card-head"><span class="skeleton" style="width:140px;height:16px"></span></div>${skelRows(6)}</div>
    </div>`;
  try {
    S.diag = await getJSON('/api/diagnostics' + (force ? '?force=1' : ''));
  } catch (err) {
    if (err && err.message === 'unauthorized') return;
    body.innerHTML = `<div class="card">${emptyState("Couldn't run diagnostics", err.message || 'Request failed')}<div style="text-align:center;margin-top:-10px"><button class="btn subtle sm" id="diag-retry">Retry</button></div></div>`;
    const rb = $('diag-retry'); if (rb) rb.onclick = () => loadDiagnostics(true);
    return;
  } finally {
    body.removeAttribute('aria-busy');
    if (rbtn) { rbtn.classList.remove('spinning'); rbtn.removeAttribute('aria-busy'); }
  }
  renderDiagnostics();
}

function diagRow(k, v) {
  return `<div class="k">${esc(k)}</div><div class="v">${v}</div>`;
}

function checkRow(c) {
  const ok = !!c.ok;
  const right = c.error
    ? `<div class="err">${esc(c.error)}</div>`
    : `<span class="pill ${ok ? 'keep' : 'delete'}">${ok ? 'OK' : 'Failed'}</span>`;
  return `<div class="check-row">
      <span class="check-ic ${ok ? 'good' : 'bad'}">${ok ? DIAG_OK : DIAG_BAD}</span>
      <div class="body"><div class="t">${esc(c.name)}</div><div class="s">${esc(c.detail || '')}</div></div>
      ${right}
    </div>`;
}

function requiredRow(r) {
  const badge = r.present == null ? '' :
    `<span class="pill ${r.present ? 'keep' : 'delete'}">${r.present ? 'Granted' : 'Missing'}</span>`;
  const ic = r.present == null
    ? '<span class="check-ic neutral"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8h.01M11 12h1v4h1"/></svg></span>'
    : `<span class="check-ic ${r.present ? 'good' : 'bad'}">${r.present ? DIAG_OK : DIAG_BAD}</span>`;
  return `<div class="check-row">
      ${ic}
      <div class="body"><div class="t">${esc(r.name)}</div><div class="s">${esc(r.purpose || '')}</div></div>
      ${badge}
    </div>`;
}

function rolesCard(d) {
  let inner;
  if (d.user_roles_error) {
    inner = `<div class="callout bad"><p>${esc(d.user_roles_error)}</p></div>`;
  } else if (!d.user_roles || !d.user_roles.length) {
    inner = '<div class="callout warn"><p>No roles were returned for your identity. You may need Reader + Cost Management Reader granted at the subscription.</p></div>';
  } else {
    inner = `<table class="diag-table">
        <thead><tr><th>Role</th><th>Scope</th><th>Type</th></tr></thead>
        <tbody>${d.user_roles.map((r) => `<tr>
          <td><b>${esc(r.role)}</b></td>
          <td class="mono">${esc(r.scope || '—')}</td>
          <td class="muted">${esc(r.scope_type || '—')}</td>
        </tr>`).join('')}</tbody>
      </table>`;
  }
  const title = d.provider === 'aws' ? 'Policies granted to you' : 'Roles granted to you';
  const sub = d.provider === 'aws' ? 'IAM policies attached to the signed-in identity' : 'Effective assignments for the signed-in identity';
  return `<div class="card"><div class="card-head"><h3>${esc(title)}</h3><div class="sub">${esc(sub)}</div></div>${inner}</div>`;
}

function renderDiagnostics() {
  const d = S.diag;
  const body = $('diag-body');
  if (!d || !body) return;
  const id = d.identity || {};
  const roleEl = $('scope-role');
  if (roleEl && d.role) roleEl.textContent = d.role;

  const kv = [];
  kv.push(diagRow('Provider', esc(providerLabel(d.provider))));
  kv.push(diagRow('Role', esc(d.role || '—')));
  const subLabel = (d.subscription && d.subscription.name) || id.account || id.name || '—';
  kv.push(diagRow('Subscription', esc(subLabel)));
  if (d.provider === 'azure') {
    kv.push(diagRow('Tenant', `<span class="mono">${esc(d.tenant || '—')}</span>`));
    kv.push(diagRow('Subscription ID', `<span class="mono">${esc((d.subscription && d.subscription.id) || '—')}</span>`));
    kv.push(diagRow('Signed-in user', esc(id.user || '—')));
    kv.push(diagRow('Your object ID', `<span class="mono">${esc(d.current_principal || '—')}</span>`));
  } else if (d.provider === 'aws') {
    kv.push(diagRow('User / Role', `<span class="mono">${esc(id.user || '—')}</span>`));
    kv.push(diagRow('ARN', `<span class="mono">${esc(id.name || '—')}</span>`));
  }

  const checks = (d.checks || []).length
    ? d.checks.map(checkRow).join('')
    : '<div class="empty" style="padding:24px"><div class="t">No checks</div><div class="s">Nothing to verify in this mode.</div></div>';

  const requiredTitle = d.provider === 'azure' ? 'Required roles (read-only)' : 'Required IAM permissions';
  const required = (d.required_access || []).length
    ? d.required_access.map(requiredRow).join('')
    : '<div class="empty" style="padding:24px"><div class="t">—</div></div>';

  const rolesBlock = (d.provider === 'azure' || d.provider === 'aws') ? rolesCard(d) : '';

  body.innerHTML = `
    <div class="grid g-2">
      <div class="card">
        <div class="card-head"><h3>Connection</h3><div class="sub">What this session is querying</div></div>
        <div class="kv">${kv.join('')}</div>
      </div>
      <div class="card">
        <div class="card-head"><h3>API checks</h3><div class="sub">Live calls made by the dashboard</div></div>
        <div class="checks">${checks}</div>
      </div>
    </div>
    <div class="grid g-2" style="margin-top:16px">
      ${rolesBlock}
      <div class="card"${rolesBlock ? '' : ' style="grid-column:1/-1"'}>
        <div class="card-head"><h3>${esc(requiredTitle)}</h3></div>
        <div class="checks">${required}</div>
      </div>
    </div>
    ${d.hint ? `<div class="callout warn" style="margin-top:16px"><h4>What to check</h4><p>${esc(d.hint)}</p></div>` : ''}`;
}

async function loadRole() {
  const el = $('scope-role');
  if (!el) return;
  try {
    const me = await getJSON('/api/auth/me');
    el.textContent = (me && me.role) || '—';
  } catch (err) {
    if (err && err.message === 'unauthorized') return;
    el.textContent = '—';
  }
}

/* ------------------------------------------------------------------ routing */
function activateView(v) {
  if (!['overview', 'cost', 'resources', 'recommendations', 'diagnostics'].includes(v)) v = 'overview';
  S.view = v;
  document.querySelectorAll('.view').forEach((el) => el.classList.toggle('active', el.id === 'view-' + v));
  document.querySelectorAll('#nav a').forEach((a) => {
    const on = a.dataset.view === v;
    a.classList.toggle('active', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  $('view-title').textContent = { overview: 'Overview', cost: 'Cost Analysis', resources: 'Resources', recommendations: 'Recommendations', diagnostics: 'Connection diagnostics' }[v];
  $('sidebar').classList.remove('open');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  ensureCharts(v);
  if (v === 'diagnostics') loadDiagnostics(false);
}

/* ------------------------------------------------------------------- theme */
function currentTheme() {
  const el = document.documentElement;
  return el && el.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
}
function applyTheme(theme, persist) {
  if (document.documentElement) document.documentElement.setAttribute('data-theme', theme);
  const btn = $('btn-theme');
  if (btn) btn.setAttribute('aria-pressed', theme === 'dark' ? 'true' : 'false');
  if (persist) { try { localStorage.setItem('ccl-theme', theme); } catch (e) {} }
  Object.keys(S.charts || {}).forEach(destroy);
  S.built = {};
  if (S.costs) ensureCharts(S.view);
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

  $('btn-refresh').onclick = () => load(true, true);
  $('btn-export').onclick = exportCsv;
  if ($('btn-diag-refresh')) $('btn-diag-refresh').onclick = () => loadDiagnostics(true);
  $('drawer-close').onclick = closeDrawer;
  $('scrim').onclick = closeDrawer;
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
  document.addEventListener('keydown', drawerKeydown);
  if ($('btn-theme')) {
    $('btn-theme').setAttribute('aria-pressed', currentTheme() === 'dark' ? 'true' : 'false');
    $('btn-theme').onclick = () => applyTheme(currentTheme() === 'dark' ? 'light' : 'dark', true);
  }
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
loadRole();
load(false);
