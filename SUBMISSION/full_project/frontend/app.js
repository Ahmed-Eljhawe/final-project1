/* ══════════════════════════════════════════════════════════
   app.js — Shared API + Chart helpers + Animated Player
   Forest & Cream theme
   ══════════════════════════════════════════════════════════ */

const API_BASE = 'http://localhost:8000';

/* ── Global state ─────────────────────────────────────────── */
window.SIM = {
  scenario:       'moderate',
  horizon:        20,
  adoptionSpeed:  1.0,
  automationRate: 5,
  country:        'WLD',
  data:           null,
};

window.simURL = (scenario) =>
  `/api/simulate/${scenario}?horizon=${window.SIM.horizon}` +
  `&adoption_speed=${window.SIM.adoptionSpeed}&country=${window.SIM.country}`;

/* ── Utility ──────────────────────────────────────────────── */
const fmt = {
  pct:    (v) => (v == null ? '—' : `${Number(v).toFixed(2)}%`),
  gdp:    (v) => (v == null ? '—' : `$${Number(v).toFixed(2)}T`),
  jobs:   (v) => (v == null ? '—' : `${(Number(v)/1e6).toFixed(2)}M`),
  number: (v, d=0) => (v == null ? '—' : Number(v).toLocaleString(undefined, {maximumFractionDigits:d, minimumFractionDigits:d})),
};

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, options);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Loading overlay + toasts ─────────────────────────────── */
function showLoading(msg = 'Loading…') {
  const el = document.getElementById('loading-overlay');
  if (el) {
    const t = el.querySelector('.loading-text');
    if (t) t.textContent = msg;
    el.classList.add('show');
  }
}
function hideLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.remove('show');
}
function toast(msg, type = 'info') {
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type]||'ℹ'}</span><span>${msg}</span>`;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

/* ── KPI updater ──────────────────────────────────────────── */
function updateKPIs(data) {
  const last = (arr) => arr && arr.length ? arr[arr.length - 1] : null;
  const kpis = {
    'kpi-jobs':     fmt.jobs(last(data.total_jobs)),
    'kpi-unem':     fmt.pct(last(data.unemployment)),
    'kpi-gdp':      fmt.gdp(last(data.gdp)),
    'kpi-ai':       fmt.pct(last(data.ai_adoption)),
    'kpi-accuracy': data.ml_forecast ? fmt.pct(data.ml_forecast.model_accuracy) : '—',
  };
  for (const [id, val] of Object.entries(kpis)) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }
}

/* ── Forest & Cream chart palette ─────────────────────────── */
const COLORS = {
  accent: '#2d5a3d',
  deep:   '#1f3a26',
  warm:   '#c4985a',
  mid:    '#5e8d73',
  soft:   '#a8c0ad',
  danger: '#a8553a',
  bright: '#4a8a5e',
  ink:    '#1f3a26',
  // multi-line palette (used when several series share a chart)
  series: ['#2d5a3d', '#c4985a', '#5e8d73', '#a8553a', '#a8c0ad'],
};

const CHART_DEFAULTS = {
  background: 'transparent',
  foreColor:  '#7a7565',
  fontFamily: "'Inter', sans-serif",
  toolbar:    { show: false },
};
const GRID_COLOR  = 'rgba(31,58,38,0.07)';
const AXIS_COLOR  = 'rgba(31,58,38,0.12)';
const AXIS_LABEL  = { style: { colors: '#7a7565', fontSize: '10px' } };

/* ── Chart helpers — MINIMAL config
 * ApexCharts has bugs with partial nested configs (legend.markers, tooltip.fixed,
 * markers.hover, etc.) where it reads offsetY on undefined nested objects.
 * Strategy: only pass top-level options. Skip legend customization, skip markers
 * customization, skip tooltip beyond enabling. Let ApexCharts use its defaults.
 * Callers can override colors and height via opts. ───────────────────────── */
function lineChart(id, series, categories, title, yFormatter = (v) => v, opts = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  const chart = new ApexCharts(el, {
    chart:   { type: 'line', height: opts.height || 240,
               toolbar: { show: false },
               fontFamily: "'Inter', sans-serif",
               foreColor: '#7a7565',
               background: 'transparent' },
    series,
    xaxis:   { categories },
    yaxis:   { labels: { formatter: yFormatter } },
    stroke:  { width: 2.5, curve: 'smooth' },
    colors:  opts.colors || ['#2d5a3d', '#c4985a', '#5e8d73', '#a8553a', '#a8c0ad'],
    grid:    { borderColor: 'rgba(31,58,38,0.07)' },
    dataLabels: { enabled: false },
    legend:  opts.showLegend === false ? { show: false } : { position: 'bottom' },
  });
  chart.render();
  return chart;
}

function areaChart(id, series, categories, title, opts = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  const chart = new ApexCharts(el, {
    chart:   { type: 'area', height: opts.height || 240,
               toolbar: { show: false },
               fontFamily: "'Inter', sans-serif",
               foreColor: '#7a7565',
               background: 'transparent' },
    series,
    fill:    { type: 'gradient', gradient: { opacityFrom: 0.35, opacityTo: 0.05 } },
    xaxis:   { categories },
    yaxis:   {},
    stroke:  { width: 2.5, curve: 'smooth' },
    colors:  opts.colors || ['#2d5a3d', '#c4985a', '#5e8d73'],
    grid:    { borderColor: 'rgba(31,58,38,0.07)' },
    dataLabels: { enabled: false },
    legend:  opts.showLegend === false ? { show: false } : { position: 'bottom' },
  });
  chart.render();
  return chart;
}

function barChart(id, series, categories, title, opts = {}) {
  const el = document.getElementById(id);
  if (!el) return;
  const chart = new ApexCharts(el, {
    chart:   { type: 'bar', height: opts.height || 260,
               toolbar: { show: false },
               fontFamily: "'Inter', sans-serif",
               foreColor: '#7a7565',
               background: 'transparent' },
    series,
    plotOptions: { bar: {
      borderRadius: 3,
      columnWidth: opts.columnWidth || '55%',
      distributed: opts.distributed || false,
    } },
    xaxis:    { categories },
    yaxis:    {},
    colors:   opts.colors || ['#2d5a3d', '#c4985a', '#5e8d73', '#a8553a'],
    grid:     { borderColor: 'rgba(31,58,38,0.07)' },
    dataLabels: { enabled: false },
    legend:   opts.showLegend === false ? { show: false } : { position: 'bottom' },
  });
  chart.render();
  return chart;
}

function donutChart(id, series, labels, title, colors) {
  const el = document.getElementById(id);
  if (!el) return;
  const chart = new ApexCharts(el, {
    chart:  { type: 'donut', height: 240,
              fontFamily: "'Inter', sans-serif",
              foreColor: '#7a7565',
              background: 'transparent' },
    series,
    labels,
    colors: colors || ['#2d5a3d','#c4985a','#5e8d73','#a8c0ad','#a8553a'],
    dataLabels: { enabled: false },
    legend: { position: 'bottom' },
    plotOptions: { pie: { donut: { size: '58%', labels: { show: false } } } },
    stroke: { width: 2, colors: ['#faf6f0'] },
  });
  chart.render();
  return chart;
}

function rangeAreaChart(id, years, lower, mean, upper, title) {
  const el = document.getElementById(id);
  if (!el) return;
  const chart = new ApexCharts(el, {
    chart:  { type: 'rangeArea', height: 320,
              toolbar: { show: false },
              fontFamily: "'Inter', sans-serif",
              foreColor: '#7a7565',
              background: 'transparent' },
    series: [
      { name: '95% CI', type: 'rangeArea', data: years.map((y, i) => ({ x: y, y: [lower[i], upper[i]] })) },
      { name: 'Mean',   type: 'line',      data: years.map((y, i) => ({ x: y, y: mean[i] })) },
    ],
    fill:   { opacity: [0.22, 1] },
    stroke: { curve: 'smooth', width: [0, 3] },
    colors: ['#2d5a3d', '#c4985a'],
    xaxis:  { type: 'numeric' },
    yaxis:  {},
    grid:   { borderColor: 'rgba(31,58,38,0.07)' },
    dataLabels: { enabled: false },
    legend: { position: 'bottom' },
  });
  chart.render();
  return chart;
}

/* ── Slider wiring ────────────────────────────────────────── */
// Keeps the WebKit track fill in sync with the slider value via --val CSS variable
function updateSliderFill(el) {
  const min = parseFloat(el.min) || 0;
  const max = parseFloat(el.max) || 100;
  const val = parseFloat(el.value);
  const pct = ((val - min) / (max - min)) * 100;
  el.style.setProperty('--val', pct + '%');
}

function wireSliders() {
  const sliders = [
    { id: 'slider-ai',         valId: 'val-ai',         key: 'adoptionSpeed' },
    { id: 'slider-automation', valId: 'val-automation', key: 'automationRate' },
    { id: 'slider-horizon',    valId: 'val-horizon',    key: 'horizon' },
  ];
  sliders.forEach(({ id, valId, key }) => {
    const el = document.getElementById(id);
    const vl = document.getElementById(valId);
    if (!el || !vl) return;
    updateSliderFill(el);   // initial paint
    el.addEventListener('input', () => {
      const v = parseFloat(el.value);
      vl.textContent = key === 'adoptionSpeed' ? v.toFixed(1) + '×' :
                       key === 'automationRate' ? v + '%' : v + ' yr';
      window.SIM[key] = v;
      updateSliderFill(el);
    });
  });
  // Catch any other range sliders on the page (e.g., Monte Carlo runs on validation.html)
  document.querySelectorAll('input[type=range]').forEach(el => {
    updateSliderFill(el);
    el.addEventListener('input', () => updateSliderFill(el));
  });
  const scen = document.getElementById('select-scenario');
  if (scen) scen.addEventListener('change', () => { window.SIM.scenario = scen.value; });
}

function highlightNav() {
  const page = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-link').forEach((a) => {
    const href = a.getAttribute('href') || '';
    a.classList.toggle('active', href === page || (page === '' && href === 'index.html'));
  });
}

async function injectCountrySelect() {
  const controls = document.querySelector('.sidebar-controls');
  if (!controls) return;
  const wrap = document.createElement('div');
  wrap.className = 'ctrl-group';
  wrap.innerHTML = `<label>Country</label><select id="select-country"><option value="WLD">World</option></select>`;
  const labelEl = controls.querySelector('.ctrl-label');
  if (labelEl && labelEl.nextSibling) controls.insertBefore(wrap, labelEl.nextSibling);
  else controls.prepend(wrap);
  try {
    const r   = await apiFetch('/api/countries');
    const sel = document.getElementById('select-country');
    sel.innerHTML = r.countries.map(c => `<option value="${c.code}">${c.name}</option>`).join('');
    sel.value = window.SIM.country;
    sel.addEventListener('change', () => { window.SIM.country = sel.value; });
  } catch (e) { console.warn('country list failed:', e); }
}

/* ── Crumb in the topbar ──────────────────────────────────── */
function updateCrumb() {
  const el = document.getElementById('crumb-state');
  if (!el) return;
  el.innerHTML = `Scenario <span class="val">${window.SIM.scenario}</span><span class="sep">/</span>` +
                 `Country <span class="val">${window.SIM.country}</span><span class="sep">/</span>` +
                 `Horizon <span class="val">${2026}–${2026 + window.SIM.horizon - 1}</span>`;
}

/* ══════════════════════════════════════════════════════════
   ANIMATED PLAYER — year-by-year playback with smooth interp
   Used by index.html (and any page that wants playback).
   ══════════════════════════════════════════════════════════ */
function createPlayer({ getData, onTick, total }) {
  // getData() -> simulation result (must already be fetched before play)
  // onTick(progress, data) -> called every animation frame with current fractional year
  // total -> number of years (data.years.length)
  const state = {
    progress: 0,
    total: total,
    tickMs: 400,
    playing: false,
    lastTime: 0,
    lastYearIdx: 0,
    rafId: null,
  };

  const els = {
    player:    document.getElementById('player'),
    btnPlay:   document.getElementById('btn-play'),
    iconPlay:  document.getElementById('icon-play'),
    iconPause: document.getElementById('icon-pause'),
    btnReset:  document.getElementById('btn-reset'),
    yearLabel: document.getElementById('year-display'),
    stepLabel: document.getElementById('step-display'),
    scrubber:  document.getElementById('scrubber'),
    fill:      document.getElementById('scrubber-fill'),
    handle:    document.getElementById('scrubber-handle'),
    ticks:     document.getElementById('scrubber-ticks'),
    speed:     document.getElementById('speed-select'),
    pill:      document.getElementById('state-pill'),
  };

  // Build tick marks
  if (els.ticks) {
    els.ticks.innerHTML = '';
    for (let i = 0; i < total; i++) {
      const t = document.createElement('div');
      t.className = 'scrubber-tick';
      els.ticks.appendChild(t);
    }
  }

  function setPill(label, cls) {
    if (!els.pill) return;
    els.pill.textContent = label;
    els.pill.className = 'state-pill ' + cls;
  }
  function setIcon(playing) {
    if (els.iconPlay)  els.iconPlay.style.display  = playing ? 'none'  : 'block';
    if (els.iconPause) els.iconPause.style.display = playing ? 'block' : 'none';
    if (els.player)    els.player.classList.toggle('is-playing', playing);
  }

  function render() {
    const data = getData();
    if (!data) return;
    const p   = state.progress;
    const lo  = Math.floor(p);
    const hi  = Math.min(lo + 1, state.total - 1);
    const t   = p - lo;

    if (els.yearLabel && data.years) {
      const visibleIdx = Math.round(p);
      els.yearLabel.textContent = data.years[visibleIdx];
      if (els.stepLabel) els.stepLabel.textContent = `YEAR ${visibleIdx + 1} / ${state.total}`;
    }

    const pct = (p / (state.total - 1)) * 100;
    if (els.fill)   els.fill.style.right = (100 - pct) + '%';
    if (els.handle) els.handle.style.left = pct + '%';

    // Flash KPIs on year boundary crossing
    const currentYearIdx = lo;
    const crossedBoundary = currentYearIdx !== state.lastYearIdx;
    if (crossedBoundary) {
      document.querySelectorAll('.kpi-card').forEach(k => {
        k.classList.remove('updated');
        void k.offsetWidth;
        k.classList.add('updated');
      });
      state.lastYearIdx = currentYearIdx;
    }

    if (onTick) onTick({ progress: p, lo, hi, t, crossedBoundary, data });
  }

  function loop(now) {
    if (!state.playing) return;
    const dt = now - state.lastTime;
    state.lastTime = now;
    state.progress += dt / state.tickMs;
    if (state.progress >= state.total - 1) {
      state.progress = state.total - 1;
      render();
      state.playing = false;
      setIcon(false);
      setPill('Done', 'done');
      state.rafId = null;
      return;
    }
    render();
    state.rafId = requestAnimationFrame(loop);
  }

  function play() {
    const data = getData();
    if (!data) { toast('Run the simulation first', 'info'); return; }
    if (state.progress >= state.total - 1 - 0.0001) {
      state.progress = 0;
      state.lastYearIdx = 0;
      render();
    }
    state.playing = true;
    state.lastTime = performance.now();
    setIcon(true);
    setPill('Playing', 'playing');
    if (state.rafId) cancelAnimationFrame(state.rafId);
    state.rafId = requestAnimationFrame(loop);
  }
  function pause() {
    if (state.rafId) cancelAnimationFrame(state.rafId);
    state.rafId = null;
    state.playing = false;
    setIcon(false);
    if (state.progress < state.total - 1 - 0.0001) setPill('Paused', 'paused');
  }
  function reset() {
    pause();
    state.progress = 0;
    state.lastYearIdx = 0;
    render();
    setPill('Idle', 'idle');
  }
  function seekTo(p) {
    const wasPlaying = state.playing;
    if (wasPlaying) pause();
    state.progress = Math.max(0, Math.min(state.total - 1, p));
    state.lastYearIdx = -1;
    render();
    state.lastYearIdx = Math.floor(state.progress);
    if (state.progress >= state.total - 1 - 0.0001) setPill('Done', 'done');
    else if (wasPlaying) play();
    else setPill('Paused', 'paused');
  }

  // Wire controls
  if (els.btnPlay)  els.btnPlay.addEventListener('click', () => state.playing ? pause() : play());
  if (els.btnReset) els.btnReset.addEventListener('click', reset);
  if (els.speed)    els.speed.addEventListener('change', (e) => {
    state.tickMs = parseInt(e.target.value);
    state.lastTime = performance.now();
  });
  if (els.scrubber) {
    let dragging = false;
    const fromEvent = (e) => {
      const rect = els.scrubber.getBoundingClientRect();
      const x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
      const pct = Math.max(0, Math.min(1, x / rect.width));
      seekTo(pct * (state.total - 1));
    };
    els.scrubber.addEventListener('mousedown', (e) => {
      dragging = true; if (state.playing) pause(); fromEvent(e);
    });
    window.addEventListener('mousemove', (e) => { if (dragging) fromEvent(e); });
    window.addEventListener('mouseup', () => { dragging = false; });
  }
  document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    if (e.code === 'Space') { e.preventDefault(); state.playing ? pause() : play(); }
    if (e.code === 'ArrowRight') { pause(); seekTo(Math.floor(state.progress) + 1); }
    if (e.code === 'ArrowLeft')  { pause(); seekTo(Math.floor(state.progress) - 1); }
    if (e.code === 'KeyR') reset();
  });

  setPill('Idle', 'idle');
  // NOTE: do NOT auto-render here. The page decides where to start — typically
  // at the end (so charts show full curves after Run, then Play "rewinds" and
  // animates). Calling seekTo(0) or seekTo(total-1) from the caller renders.
  return { play, pause, reset, seekTo, render, getState: () => state };
}

// Linear interpolation (used by chart updates in playback)
function lerp(a, b, t) { return a + (b - a) * t; }
function valueAt(arr, progress) {
  const lo = Math.floor(progress);
  const hi = Math.min(lo + 1, arr.length - 1);
  return lerp(arr[lo], arr[hi], progress - lo);
}

// Slice an array up to the current fractional year, with one interpolated tip.
// Useful for growing line/area charts year-by-year during playback.
function growSeries(arr, progress) {
  const lo = Math.floor(progress);
  const hi = Math.min(lo + 1, arr.length - 1);
  const t  = progress - lo;
  const out = arr.slice(0, lo + 1);
  if (t > 0 && lo < arr.length - 1) {
    out.push(arr[lo] + (arr[hi] - arr[lo]) * t);
  }
  return out;
}

/* ──────────────────────────────────────────────────────────
 * Inject the year-by-year animated player markup into a page.
 * Call from any page after page-header — the player goes right
 * after the supplied anchor element. No-op if already present.
 * ────────────────────────────────────────────────────────── */
function injectPlayerMarkup(anchorEl) {
  if (!anchorEl) return;
  if (document.getElementById('player')) return;  // already on page
  const html = `
    <div class="player" id="player">
      <button class="btn" id="btn-play" title="Play / Pause (Space)">
        <svg id="icon-play"  viewBox="0 0 24 24" style="display:block"><path d="M8 5v14l11-7z"/></svg>
        <svg id="icon-pause" viewBox="0 0 24 24" style="display:none"><path d="M6 4h4v16H6zm8 0h4v16h-4z"/></svg>
      </button>
      <button class="btn secondary" id="btn-reset" title="Reset (R)">
        <svg viewBox="0 0 24 24"><path d="M12 5V1L7 6l5 5V7c3.3 0 6 2.7 6 6s-2.7 6-6 6-6-2.7-6-6H4c0 4.4 3.6 8 8 8s8-3.6 8-8-3.6-8-8-8z"/></svg>
      </button>
      <div class="year-display">
        <span class="year" id="year-display">—</span>
        <span class="step" id="step-display">YEAR 1 / 1</span>
      </div>
      <div class="scrubber" id="scrubber">
        <div class="scrubber-track"><div class="scrubber-fill" id="scrubber-fill"></div></div>
        <div class="scrubber-ticks" id="scrubber-ticks"></div>
        <div class="scrubber-handle" id="scrubber-handle"></div>
        <div class="scrubber-labels" id="scrubber-labels"></div>
      </div>
      <div class="speed">Speed
        <select id="speed-select">
          <option value="800">0.5×</option>
          <option value="400" selected>1×</option>
          <option value="200">2×</option>
          <option value="100">4×</option>
        </select>
      </div>
      <span class="state-pill idle" id="state-pill">Idle</span>
    </div>`;
  anchorEl.insertAdjacentHTML('afterend', html);
}

// Update scrubber-labels to show 5 evenly-spaced years from the data
function updateScrubberLabels(years) {
  const el = document.getElementById('scrubber-labels');
  if (!el || !years || years.length === 0) return;
  const n = years.length;
  const idxs = [0, Math.floor((n - 1) * 0.25), Math.floor((n - 1) * 0.5),
                   Math.floor((n - 1) * 0.75), n - 1];
  el.innerHTML = idxs.map(i => `<span>${years[i]}</span>`).join('');
}

/* ── DOM ready ────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  wireSliders();
  highlightNav();
  injectCountrySelect();
  updateCrumb();
});
