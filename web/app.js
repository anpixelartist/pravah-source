/* Pravah — map-first command centre.
   The map is the home; one slide-in panel shows a single task at a time (Overview, a
   junction, Priorities, Deploy, Forecast, Adjust). Pressure recompute mirrors pressure.py
   so the "Adjust" sliders re-rank the city live and match the Python engine at the
   recommended weights. Plain language throughout. Forecast = the interpretable model (AI).
   Offline-first (window.PRAVAH_DATA). */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const fmt = (n) => Math.round(n).toLocaleString();
  const signpct = (n) => (n > 0 ? "+" : "") + Math.round(n) + "%";
  const isMobile = () => matchMedia('(max-width:680px)').matches;

  async function load() {
    if (window.PRAVAH_DATA) return window.PRAVAH_DATA;
    try { const r = await fetch('./data/aggregates.json'); return await r.json(); }
    catch (e) { document.body.innerHTML =
      '<p style="font-family:sans-serif;padding:30px">Could not load data. Run ' +
      '<code>make aggregates</code>, or open via <code>make web</code>.</p>'; throw e; }
  }

  // ---- pressure recompute (mirrors pressure.py) ----
  function norm(vals) { const mn = Math.min(...vals), mx = Math.max(...vals), rng = mx - mn;
    return vals.map((v) => (rng > 1e-9 ? (v - mn) / rng : 0)); }
  function officersFor(p) { return p >= 85 ? 3 : p >= 60 ? 2 : 1; }
  function sameWeights(a, b) { const s1 = a.chronic + a.blindness + a.volume, s2 = b.chronic + b.blindness + b.volume;
    return ['chronic', 'blindness', 'volume'].every((k) => Math.abs(a[k] / s1 - b[k] / s2) < 1e-6); }
  function recompute(junctions, w) {
    if (ST.data && sameWeights(w, ST.data.meta.weights))
      return [...junctions].sort((a, b) => b.pressure - a.pressure);
    const s = w.chronic + w.blindness + w.volume || 1;
    const wc = w.chronic / s, wb = w.blindness / s, wv = w.volume / s;
    const nc = norm(junctions.map((j) => Math.log1p(j.cost)));
    const nv = norm(junctions.map((j) => Math.log1p(j.n)));
    const maxEve = Math.max(...junctions.map((j) => j.eve_share));
    return junctions.map((j, i) => {
      const blindness = maxEve > 0 ? 1 - j.eve_share / maxEve : 0;
      const pc = 100 * wc * nc[i], pb = 100 * wb * blindness, pv = 100 * wv * nv[i];
      const pressure = Math.max(0, Math.min(100, Math.round(pc + pb + pv)));
      return { ...j, pc: +pc.toFixed(1), pb: +pb.toFixed(1), pv: +pv.toFixed(1), pressure, req: officersFor(pressure) };
    }).sort((a, b) => b.pressure - a.pressure);
  }
  function heat(p) {
    p = Math.max(0, Math.min(100, p)) / 100;
    const A = [15, 182, 166], B = [245, 165, 36], C = [240, 67, 106];
    let a, b, t; if (p < 0.5) { a = A; b = B; t = p / 0.5; } else { a = B; b = C; t = (p - 0.5) / 0.5; }
    const m = (i) => Math.round(a[i] + (b[i] - a[i]) * t);
    return `rgb(${m(0)},${m(1)},${m(2)})`;
  }

  const ST = { data: null, J: [], weights: { chronic: 0.5, blindness: 0.3, volume: 0.2 },
    sel: null, off: 18, panel: null };

  // ---- map: projection + camera (zoom + pan) ----
  const PAD = 0.06, SS = 2.4;          // base padding; basemap supersample (crisp when zoomed)
  const cam = { s: 1, tx: 0, ty: 0 };
  let mapW = 0, mapH = 0, roadCanvas = null, heatCanvas = null;
  let nodeEls = [], phEls = [];

  function proj(lat, lon) {
    const [la0, la1, lo0, lo1] = ST.data.kpi.bbox;
    return { x: (PAD + (1 - 2 * PAD) * (lon - lo0) / (lo1 - lo0)) * 100,
      y: (PAD + (1 - 2 * PAD) * (la1 - lat) / (la1 - la0)) * 100 };
  }
  function basePx(lat, lon) { const q = proj(lat, lon); return [q.x / 100 * mapW, q.y / 100 * mapH]; }
  function toScreen(lat, lon) { const [bx, by] = basePx(lat, lon); return [bx * cam.s + cam.tx, by * cam.s + cam.ty]; }

  function buildBaseLayers() {                 // built once per size — streets + density raster
    const map = $('#map'); mapW = map.clientWidth; mapH = map.clientHeight;
    // streets (water + roads) at supersample so they stay crisp when zoomed in
    roadCanvas = document.createElement('canvas');
    roadCanvas.width = Math.round(mapW * SS); roadCanvas.height = Math.round(mapH * SS);
    const rg = roadCanvas.getContext('2d'); rg.scale(SS, SS);
    const BM = window.PRAVAH_BASEMAP;
    if (BM) {
      rg.fillStyle = '#dce8f7';
      for (const poly of BM.water) { rg.beginPath();
        poly.forEach(([lo, la], i) => { const [x, y] = basePx(la, lo); i ? rg.lineTo(x, y) : rg.moveTo(x, y); });
        rg.closePath(); rg.fill(); }
      rg.lineCap = 'round'; rg.lineJoin = 'round';
      const styles = { 3: ['#d2d9e8', 0.55], 2: ['#b8c1d6', 1.0], 1: ['#94a1bd', 1.8] };
      for (const rank of [3, 2, 1]) {
        rg.strokeStyle = styles[rank][0]; rg.lineWidth = styles[rank][1]; rg.beginPath();
        for (const [rk, pts] of BM.roads) { if (rk !== rank) continue;
          pts.forEach(([lo, la], i) => { const [x, y] = basePx(la, lo); i ? rg.lineTo(x, y) : rg.moveTo(x, y); }); }
        rg.stroke();
      }
    }
    // density heat (subtle violation concentration, blurred)
    heatCanvas = document.createElement('canvas'); heatCanvas.width = mapW; heatCanvas.height = mapH;
    const hg = heatCanvas.getContext('2d'), D = ST.data.density;
    if (D) {
      const [la0, la1, lo0, lo1] = D.bbox, gw = D.w, gh = D.h, ref = D.max * 0.14, cw = (mapW / gw) * 2.3;
      hg.filter = 'blur(6px)';
      for (const [i, cnt] of D.cells) {
        const ix = i % gw, iy = (i / gw) | 0;
        const lon = lo0 + (ix + 0.5) / gw * (lo1 - lo0), lat = la1 - (iy + 0.5) / gh * (la1 - la0);
        const [px, py] = basePx(lat, lon);
        const a = Math.max(0.02, Math.min(0.26, Math.sqrt(cnt / ref) * 0.27));
        hg.fillStyle = `rgba(98,116,182,${a})`; hg.fillRect(px - cw / 2, py - cw / 2, cw, cw);
      }
      hg.filter = 'none';
    }
    clampCam();
  }

  function clampCam() {
    cam.s = Math.max(1, Math.min(9, cam.s));
    cam.tx = Math.max(mapW - mapW * cam.s, Math.min(0, cam.tx));
    cam.ty = Math.max(mapH - mapH * cam.s, Math.min(0, cam.ty));
  }
  function zoomAt(cx, cy, factor) {
    const ns = Math.max(1, Math.min(9, cam.s * factor)), k = ns / cam.s;
    cam.tx = cx - (cx - cam.tx) * k; cam.ty = cy - (cy - cam.ty) * k; cam.s = ns; clampCam(); render();
  }

  function drawWorld() {
    const c = $('#glow'), dpr = Math.min(2, devicePixelRatio || 1);
    if (c.width !== Math.round(mapW * dpr)) {
      c.width = mapW * dpr; c.height = mapH * dpr; c.style.width = mapW + 'px'; c.style.height = mapH + 'px';
    }
    const g = c.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, mapW, mapH);
    g.save(); g.translate(cam.tx, cam.ty); g.scale(cam.s, cam.s);
    if (heatCanvas) {                            // density UNDER the streets, faded as you zoom in
      const fc = ST.panel === 'forecast' ? 0.4 : 1;   // calm the heat so forecast markers read
      g.globalAlpha = Math.max(0.2, 1 - (cam.s - 1) * 0.17) * fc; g.drawImage(heatCanvas, 0, 0, mapW, mapH); g.globalAlpha = 1;
    }
    if (roadCanvas) g.drawImage(roadCanvas, 0, 0, mapW, mapH);
    g.restore();
    g.textBaseline = 'middle'; g.textAlign = 'left'; g.font = '600 11px Inter, system-ui, sans-serif';
    for (const ar of ST.data.areas) {
      const [x, y] = toScreen(ar.lat, ar.lon);
      if (x < -40 || x > mapW + 60 || y < -16 || y > mapH + 16) continue;
      g.fillStyle = 'rgba(40,52,84,0.5)'; g.beginPath(); g.arc(x, y, 2.6, 0, 7); g.fill();
      g.lineWidth = 3; g.strokeStyle = 'rgba(255,255,255,0.92)';
      g.strokeText(ar.name, x + 7, y); g.fillStyle = '#51607e'; g.fillText(ar.name, x + 7, y);
    }
    updateScale();
  }
  function updateScale() {
    const [, , lo0, lo1] = ST.data.kpi.bbox;
    const kmPerLon = 111 * Math.cos(13 * Math.PI / 180);     // Bengaluru ≈ 13°N
    const pxPerKm = (((1 - 2 * PAD) * mapW) / ((lo1 - lo0) * kmPerLon)) * cam.s;
    let km = 1; for (const t of [1, 2, 5, 10, 20]) if (t * pxPerKm <= 100) km = t;
    const bar = $('#sbar'), lbl = $('#slbl');
    if (bar) { bar.style.width = Math.round(km * pxPerKm) + 'px'; lbl.textContent = km + ' km'; }
  }
  const tip = $('#tip');
  function showTip(e, j) {
    const fc = j.fc ? `<div class="row"><span>Next week</span><span style="color:${j.fc.dir === 'up' ? 'var(--coral)' : j.fc.dir === 'down' ? 'var(--teal)' : 'var(--tx-2)'}">${j.fc.dir === 'up' ? 'rising' : j.fc.dir === 'down' ? 'easing' : 'steady'} ${signpct(j.fc.delta_pct)}</span></div>` : '';
    tip.innerHTML = `<b>${j.name}</b>` +
      `<div class="row"><span>Pressure</span><span style="color:${heat(j.pressure)}">${j.pressure}/100</span></div>` +
      `<div class="row"><span>Cases</span><span>${j.n.toLocaleString()}</span></div>` +
      `<div class="row"><span>Caught after 3pm</span><span style="color:var(--coral)">${j.eve_share}%</span></div>` + fc;
    tip.classList.add('on'); moveTip(e);
  }
  function moveTip(e) { let x = e.clientX + 16, y = e.clientY + 16;
    if (x + 262 > innerWidth) x = e.clientX - 262; if (y + 150 > innerHeight) y = e.clientY - 150;
    tip.style.left = x + 'px'; tip.style.top = y + 'px'; }
  function hideTip() { tip.classList.remove('on'); }

  function createNodes() {                      // (re)build the dot + phantom DOM (data/weights changed)
    const map = $('#map');
    map.querySelectorAll('.node,.ph').forEach((n) => n.remove());
    nodeEls = []; phEls = [];
    ST.data.phantom.forEach((p) => { const d = document.createElement('div'); d.className = 'ph';
      map.appendChild(d); phEls.push({ el: d, p }); });
    ST.J.forEach((j) => {
      const sz = 9 + Math.sqrt(j.n) / 8, d = document.createElement('div');
      d.className = 'node'; d.style.width = sz + 'px'; d.style.height = sz + 'px'; d.style.background = heat(j.pressure);
      d.tabIndex = 0; d.setAttribute('role', 'button');
      d.setAttribute('aria-label', `${j.name}, pressure ${j.pressure} of 100`);
      d.addEventListener('mouseenter', (e) => showTip(e, j));
      d.addEventListener('mousemove', moveTip);
      d.addEventListener('mouseleave', hideTip);
      d.addEventListener('click', (e) => { e.stopPropagation(); select(j.name); });
      d.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(j.name); } });
      map.appendChild(d); nodeEls.push({ el: d, j });
    });
  }
  function positionNodes() {                    // place dots under the current camera (cheap)
    const fcView = ST.panel === 'forecast';
    for (const { el, p } of phEls) { const [x, y] = toScreen(p.lat, p.lon);
      el.style.left = x + 'px'; el.style.top = y + 'px';
      // hide phantom rings in Forecast view so the coral 'rising' markers read clearly
      el.style.display = (fcView || x < -20 || x > mapW + 20 || y < -20 || y > mapH + 20) ? 'none' : ''; }
    for (const { el, j } of nodeEls) { const [x, y] = toScreen(j.lat, j.lon);
      el.style.left = x + 'px'; el.style.top = y + 'px'; el.classList.toggle('sel', ST.sel === j.name);
      // when the Forecast panel is open, light up the junctions the model says will worsen
      el.classList.toggle('rising', fcView && !!j.fc && j.fc.dir === 'up');
      el.classList.toggle('dim', fcView && !(j.fc && j.fc.dir === 'up'));
      el.style.display = (x < -30 || x > mapW + 30 || y < -30 || y > mapH + 30) ? 'none' : ''; }
  }
  let rafPending = false;
  function render() { if (rafPending) return; rafPending = true;
    requestAnimationFrame(() => { rafPending = false; drawWorld(); positionNodes(); }); }
  function renderMap() { createNodes(); render(); }

  // ---- enforcement-by-hour timeline (rendered into the Overview panel) ----
  function hourChart() {
    const h = ST.data.hourly, max = Math.max(...h);
    const W = 340, H = 152, padL = 4, padR = 4, top = 24, base = H - 26;
    const n = 24, gap = 3, bw = (W - padL - padR - gap * (n - 1)) / n;
    const xAt = (i) => padL + i * (bw + gap);
    let s = `<rect x="${xAt(15) - gap / 2}" y="${top - 8}" width="${(bw + gap) * 7}" height="${base - top + 14}" rx="7" fill="#f0436a" opacity="0.07"/>`;
    for (let i = 0; i < 24; i++) {
      const bh = Math.max(2, (h[i] / max) * (base - top)), x = xAt(i), y = base - bh;
      const ev = i >= 15 && i <= 21, peak = i >= 8 && i <= 11;
      const col = ev ? '#f0436a' : peak ? '#0fb6a6' : '#cad2e6';
      s += `<rect x="${x}" y="${y}" width="${bw}" height="${bh}" rx="${Math.min(3, bw / 2)}" fill="${col}"/>`;
    }
    s += `<line x1="${padL}" y1="${base + 0.5}" x2="${W - padR}" y2="${base + 0.5}" stroke="#e6e9f3"/>`;
    const lab = (i, t) => `<text x="${xAt(i) + bw / 2}" y="${H - 8}" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#909bb4">${t}</text>`;
    s += lab(0, '12a') + lab(6, '6a') + lab(12, '12p') + lab(18, '6p') + lab(23, '11p');
    s += `<text x="${xAt(18)}" y="${top - 11}" text-anchor="middle" font-family="Inter" font-weight="600" font-size="10" fill="#e03a60">evening blind window</text>`;
    return `<svg class="hourchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Tickets by hour of day — collapses after 3pm">${s}</svg>`;
  }

  // ---- panels ----
  const TITLES = { brief: 'Overview', priorities: 'Priority list', deploy: 'Where to send officers',
    forecast: 'Next-week forecast', adjust: 'What matters', junction: 'Junction' };

  function renderBrief() {
    const k = ST.data.kpi, mc = ST.data.model || {};
    const kpis = [
      { v: k.total.toLocaleString(), l: 'parking cases analysed', c: 'good', b: 'fact' },
      { v: k.eve_pct + '%', l: 'caught in the 3–9pm rush', c: 'alert', b: 'fact' },
      { v: k.n_phantom, l: 'busy spots off the official radar', c: 'warn', b: 'fact' },
      { v: (mc.n_rising ?? 0), l: 'junctions set to worsen next week', c: 'ai', b: 'ai' },
    ].map((x) => `<div class="kpi ${x.c}"><div class="v">${x.v} <span class="badge ${x.b}">${x.b.toUpperCase()}</span></div><div class="l">${x.l}</div></div>`).join('');
    return `<div class="kpis">${kpis}</div>` +
      `<div class="storyline">Over ${k.weeks} weeks the city wrote <b>${k.total.toLocaleString()}</b> parking cases — ` +
      `yet only <b>${k.eve_pct}%</b> land in the 3–9pm rush. That evening blind spot, not a lack of violations, is the gap.</div>` +
      `<div class="slab">When tickets happen <span class="badge fact">FACT</span></div>` +
      `<div class="clockstat"><span class="cv">${k.eve_pct}%</span><span class="cl">of all tickets land in the <b>3–9pm</b> rush — exactly when congestion peaks</span></div>` +
      hourChart() +
      `<div class="clocknote">Enforcement peaks 8am–noon, then <b>goes dark after 3pm</b>. Yet junctions that ` +
      `<span class="hl">are</span> watched in the evening still write ~${k.covered_eve}% of their tickets then — so this ` +
      `is an <b>enforcement gap, not reality</b>. An estimated <b>~${(k.hidden_est / 1000).toFixed(0)}k</b> evening ` +
      `cases go unseen each window (EST).</div>` +
      `<div class="slab" style="margin-top:18px">Honest about the data</div>` +
      `<ul class="limits">` +
      `<li><b>Tickets only exist where officers stood.</b> Un-patrolled spots read as zero — not clean, just unseen. We correct with coverage-normalised features and the blind-spot term, and treat the blind spot as the finding.</li>` +
      `<li><b>Timestamps are filing-time, not occurrence-time.</b> So our evening case rests on a control: watched junctions still write ~${k.covered_eve}% of tickets in the evening — when officers are there, evenings get caught.</li>` +
      `<li><b>~${k.reject_pct ?? 30}% of tickets are rejected or disputed.</b> Every junction shows its own rejection rate as a confidence flag, and low-confidence scores are tagged so you don't over-trust them.</li>` +
      `</ul>`;
  }

  function renderPriorities() {
    return ST.J.map((j, i) => {
      let fcm = '';
      if (j.fc && j.fc.dir !== 'flat') fcm = `<span class="${j.fc.dir}">${signpct(j.fc.delta_pct)} next wk</span>`;
      return `<div class="qrow ${ST.sel === j.name ? 'sel' : ''}" data-name="${j.name}" tabindex="0" role="button" aria-label="${j.name}, pressure ${j.pressure}">
        <div class="rk">${i + 1}</div>
        <div><div class="nm">${j.name}</div><div class="meta"><span>${j.n.toLocaleString()} cases</span><span class="blind">${j.eve_share}% eve</span>${fcm}</div></div>
        <div class="pv" style="background:${heat(j.pressure)}">${j.pressure}</div></div>`;
    }).join('');
  }

  function renderJunction(name) {
    const j = ST.J.find((x) => x.name === name);
    if (!j) return '<div class="empty">Junction not found.</div>';
    const tot = Math.max(j.pc + j.pb + j.pv, 0.001);
    const seg = (v, cls, lbl) => v > 4 ? `<div class="${cls}" style="width:${100 * v / tot}%">${lbl}</div>` : '';
    let fc = '';
    if (j.fc) {
      const label = j.fc.dir === 'up' ? 'likely to get worse' : j.fc.dir === 'down' ? 'likely to ease' : 'about steady';
      const why = j.fc.reasons && j.fc.reasons.length ? ` Mostly down to <span class="wy">${j.fc.reasons.join(' and ')}</span>.` : '';
      fc = `<div class="fccard"><span class="ar ${j.fc.dir}">${signpct(j.fc.delta_pct)}</span><div class="ft"><b>Next week: ${label}</b> <span class="badge ai">AI</span>${why}</div></div>`;
    }
    const ev = (j.evidence || []).map((r) =>
      `<div class="ev"><span>${r.t}</span><span>${r.o} · ${r.v}</span><span class="${/approv/i.test(r.s) ? 'ok' : (/reject/i.test(r.s) ? 'no' : '')}">${r.s}</span></div>`).join('')
      || '<div class="note">No sample tickets exported for this junction.</div>';
    const rr = j.reject_rate ?? 0;        // data-confidence: rejection rate among decided tickets
    const cf = rr >= 45 ? ['low', '⚠', ' Lean on the raw tickets below, not just the score.']
      : rr >= 25 ? ['medium', '•', ''] : ['high', '✓', ''];
    const conf = `<div class="conf ${cf[0]}"><span class="ci">${cf[1]}</span><div>Data confidence: <b>${cf[0]}</b> ` +
      `<span class="badge fact">FACT</span> · ${rr}% of decided tickets here were rejected.${cf[2]}</div></div>`;
    return `<div class="jh"><div class="jscore" style="background:${heat(j.pressure)}"><span class="n">${j.pressure}</span><span class="u">SCORE</span></div>` +
      `<div class="jmeta"><div class="jt">${j.name}</div><div class="js">${j.ps ? j.ps + ' police station · ' : ''}most common: ${j.top}</div></div></div>` +
      `<div class="bbar">${seg(j.pc, 'seg-c', 'parking')}${seg(j.pb, 'seg-b', 'blind')}${seg(j.pv, 'seg-v', 'cases')}</div>` +
      `<div class="partkey">` +
      `<span><i class="seg-c"></i><b>${Math.round(j.pc)}</b> from how bad the parking is <span class="badge fact">FACT</span></span>` +
      `<span><i class="seg-b"></i><b>${Math.round(j.pb)}</b> from the evening blind spot <span class="badge fact">FACT</span></span>` +
      `<span><i class="seg-v"></i><b>${Math.round(j.pv)}</b> from the number of cases <span class="badge fact">FACT</span></span></div>` +
      fc +
      `<div class="recline">Send <b>${j.req} officer${j.req > 1 ? 's' : ''}</b> here — about <b>${fmt(j.rec)} hours</b> of stuck traffic cleared a week <span class="badge est">EST</span>.</div>` +
      conf +
      `<div class="slab">Recent tickets behind this score <span class="badge fact">FACT</span></div>${ev}` +
      `<div class="cf">Skip ${j.name} and you give up ~${fmt(j.rec)} hours of stuck traffic cleared every week (EST).</div>`;
  }

  function renderForecastBody() {
    const mc = ST.data.model;
    if (!mc) return '<div class="empty">Model output unavailable.</div>';
    const m = mc.metrics;
    const imp = Object.entries(mc.importances).slice(0, 5).map(([name, v]) => {
      const pct = Math.round(v * 100);
      return `<div class="improw"><span class="il">${name}</span><span class="track"><span class="fill" style="width:${Math.max(4, pct)}%"></span></span><span class="pct">${pct}%</span></div>`;
    }).join('');
    const risers = ST.J.filter((j) => j.fc && j.fc.dir === 'up').sort((a, b) => b.fc.delta_pct - a.fc.delta_pct);
    const list = risers.length ? risers.map((j) => {
      const why = j.fc.reasons && j.fc.reasons.length ? `Mostly ${j.fc.reasons.join(' and ')}.` : '';
      return `<div class="riser ${j.fc.dir}" data-name="${j.name}" tabindex="0" role="button" aria-label="${j.name}, ${signpct(j.fc.delta_pct)} next week, tap to locate">
        <span class="rn">${j.name}</span><span class="rd ${j.fc.dir}">${signpct(j.fc.delta_pct)} <span class="loc">locate ›</span></span>
        <span class="rw">${why} Pressure today ${j.pressure}/100.</span></div>`;
    }).join('') : '<div class="note">No junctions are predicted to worsen next week.</div>';
    return `<div class="usebar">Use this to <b>pre-position officers before next week</b>. The ${mc.n_rising} junctions ` +
      `the model expects to worsen are <b style="color:var(--coral)">ringed in coral on the map</b> right now — ` +
      `tap any one (here or on the map) to see it and its plan.</div>` +
      `<div class="r2big"><div class="r2">${m.r2}</div><div class="r2l">accuracy (R²) on weeks <b>${m.test_weeks[0]}–${m.test_weeks[m.test_weeks.length - 1]}</b> the model never saw while training <span class="badge ai">AI</span></div></div>` +
      `<div class="mstats">` +
      `<div class="mstat win"><div class="v">+${m.improvement_pct}%</div><div class="k">more accurate than "next week = last week"</div></div>` +
      `<div class="mstat"><div class="v">${m.baseline_r2}</div><div class="k">that naive baseline's R²</div></div>` +
      `<div class="mstat"><div class="v">${m.n_test.toLocaleString()}</div><div class="k">held-out predictions graded</div></div>` +
      `<div class="mstat"><div class="v">${mc.n_rising}</div><div class="k">junctions flagged as worsening</div></div></div>` +
      `<div class="slab">What the forecast leans on</div>${imp}` +
      `<div class="slab">Predicted to worsen next week <span class="badge ai">AI</span> · tap to locate</div>${list}` +
      `<div class="note">Interpretable gradient-boosted trees + SHAP — never a neural net, so every call can be ` +
      `explained. This is the model's own call — independent of the priority sliders.</div>`;
  }

  function renderDeployStatic() {
    return `<div class="sliderrow"><span class="n" id="offN">${ST.off}</span><span class="l">officers available</span></div>` +
      `<input type="range" min="2" max="40" value="${ST.off}" id="off" aria-label="Officers available">` +
      `<div id="depout"></div>`;
  }
  function allocate(rows, n) { let used = 0, rec = 0; const picks = [];
    for (const r of rows) { if (used + r.req <= n) { used += r.req; rec += r.rec; picks.push(r); } if (used >= n) break; } return { rec, picks }; }
  function knapsack(rows, n) { const cap = n | 0, dp = new Array(cap + 1).fill(0), keep = rows.map(() => new Array(cap + 1).fill(false));
    rows.forEach((r, i) => { const w = r.req | 0, v = r.rec; for (let c = cap; c >= w; c--) if (dp[c - w] + v > dp[c]) { dp[c] = dp[c - w] + v; keep[i][c] = true; } });
    let c = cap; const picks = []; for (let i = rows.length - 1; i >= 0; i--) if (keep[i][c]) { picks.push(rows[i]); c -= rows[i].req | 0; }
    picks.reverse(); return { rec: dp[cap], picks }; }
  function updateDeploy() {
    const n = ST.off; const out = $('#depout'); if (!out) return;
    $('#offN').textContent = n;
    const base = allocate([...ST.J].sort((a, b) => b.n - a.n), n);
    const pra = knapsack(ST.J, n); pra.picks.sort((a, b) => b.pressure - a.pressure);
    const d = base.rec ? Math.round(100 * (pra.rec - base.rec) / base.rec) : 0;
    const zones = new Set(ST.J.map((j) => j.ps).filter(Boolean));
    const covered = new Set(pra.picks.map((j) => j.ps).filter(Boolean));
    const share = zones.size ? covered.size / zones.size : 1;
    const eq = share < 0.5
      ? `<div class="equity warn"><span class="ei">⚠</span><div>This plan touches ${covered.size} of ${zones.size} police-station areas. Concentrated — review so whole areas aren't left unwatched.</div></div>`
      : `<div class="equity ok"><span class="ei">✓</span><div>Fairness: ${covered.size} of ${zones.size} areas covered. Spread looks reasonable.</div></div>`;
    out.innerHTML =
      `<div class="compare"><div class="comp"><div class="h">Today's way<br>most tickets</div><div class="v">${fmt(base.rec)} <span class="badge est">EST</span></div></div>` +
      `<div class="comp win"><div class="h">Pravah<br>most time saved</div><div class="v">${fmt(pra.rec)} <span class="badge est">EST</span></div></div></div>` +
      `<div class="delta"><b>+${d}%</b> more stuck-traffic hours cleared, same officers <span class="badge est">EST</span><div class="note" style="margin-top:5px">The bigger win: Pravah's picks include the evening blind hours and phantom spots today's ticket-led patrols never see.</div></div>` +
      `<div class="slab">The plan · a reason on every pick</div>` +
      pra.picks.map((j) => { const blind = j.eve_share < 2 ? ' — and it\'s an evening blind spot' : '';
        return `<div class="arow"><div class="l1"><span class="o">${j.req} officer${j.req > 1 ? 's' : ''}</span><span class="nm">${j.name}</span><span class="r">${fmt(j.rec)} hrs/wk</span></div><div class="why">Pressure ${j.pressure}/100; about ${fmt(j.rec)} hours of stuck traffic cleared a week${blind}.</div></div>`; }).join('') +
      eq +
      `<div class="note">Officers placed to clear the most stuck-traffic hours. "Time saved" is an estimate of network delay relieved when a junction's persistent illegal parking is cleared. Pravah recommends — an officer decides.</div>`;
  }

  function renderAdjust() {
    const defs = [['chronic', 'How bad the parking is', 'big vehicles, main roads, footpaths'],
      ['blindness', 'Evening blind spot', 'how little it is checked after 3pm'],
      ['volume', 'Number of cases', 'sheer count of tickets']];
    return `<div class="usebar">Decide what "worst" means. Drag a slider and the whole city re-ranks instantly — ` +
      `the map recolours and this <b>live top-5 reorders</b> in front of you. ▲▼ shows each junction's move ` +
      `vs the recommended weighting.</div>` +
      defs.map(([k, nm, hint]) => `<div class="wrow"><div class="top"><span class="nm">${nm}</span><span class="val" id="wv-${k}"></span></div>` +
        `<input type="range" min="0" max="100" id="w-${k}" aria-label="${nm} importance"><div class="hint">${hint}</div></div>`).join('') +
      `<button class="resetw" id="resetw">Reset to recommended</button>` +
      `<div class="slab" style="margin-top:20px">Top priorities right now</div><div class="wpreview" id="wpreview"></div>`;
  }
  function updateWPreview() {
    const el = $('#wpreview'); if (!el) return;
    const def = {}; ST.data.junctions.forEach((j, i) => { def[j.name] = i; });   // recommended-weight order
    el.innerHTML = ST.J.slice(0, 5).map((j, i) => {
      const mv = (def[j.name] ?? i) - i;     // +ve = moved up vs the recommended ranking
      const tag = mv > 0 ? `<span class="mv up">▲${mv}</span>` : mv < 0 ? `<span class="mv down">▼${-mv}</span>` : '<span class="mv flat">—</span>';
      return `<div class="wprow ${i === 0 ? 'top' : ''}"><span class="rk">${i + 1}</span>` +
        `<span class="nm">${j.name}</span>${tag}<span class="pv" style="background:${heat(j.pressure)}">${j.pressure}</span></div>`;
    }).join('');
  }
  function wireAdjust() {
    const sync = () => { const s = ST.weights.chronic + ST.weights.blindness + ST.weights.volume || 1;
      ['chronic', 'blindness', 'volume'].forEach((k) => { $('#w-' + k).value = Math.round(ST.weights[k] * 100);
        $('#wv-' + k).textContent = Math.round(100 * ST.weights[k] / s) + '%'; }); };
    sync(); updateWPreview();
    ['chronic', 'blindness', 'volume'].forEach((k) => $('#w-' + k).addEventListener('input', () => {
      ST.weights[k] = (+$('#w-' + k).value) / 100;
      const s = ST.weights.chronic + ST.weights.blindness + ST.weights.volume || 1;
      ['chronic', 'blindness', 'volume'].forEach((kk) => $('#wv-' + kk).textContent = Math.round(100 * ST.weights[kk] / s) + '%');
      rerank();
    }));
    $('#resetw').addEventListener('click', () => { ST.weights = { ...ST.data.meta.weights }; sync(); rerank(); });
  }

  // ---- panel controller ----
  function openPanel(name, arg) {
    ST.panel = name;
    $('#ptitle').textContent = name === 'junction' ? (arg || 'Junction') : TITLES[name];
    const body = $('#pbody');
    if (name === 'brief') body.innerHTML = renderBrief();
    else if (name === 'priorities') body.innerHTML = renderPriorities();
    else if (name === 'forecast') body.innerHTML = renderForecastBody();
    else if (name === 'adjust') { body.innerHTML = renderAdjust(); wireAdjust(); }
    else if (name === 'deploy') { body.innerHTML = renderDeployStatic(); $('#off').addEventListener('input', () => { ST.off = +$('#off').value; updateDeploy(); }); updateDeploy(); }
    else if (name === 'junction') body.innerHTML = renderJunction(arg);
    body.scrollTop = 0;
    $('#panel').classList.add('on'); $('#panel').setAttribute('aria-hidden', 'false');
    $('#hint').style.display = 'none';
    if (isMobile()) $('#scrim').classList.add('on');
    $$('.nav button').forEach((b) => b.classList.toggle('active', b.dataset.panel === name));
    render();   // refresh map markers (forecast 'rising' highlight, selection) for the new panel
  }
  function closePanel() {
    ST.panel = null; ST.sel = null;
    $('#panel').classList.remove('on'); $('#panel').setAttribute('aria-hidden', 'true');
    $('#scrim').classList.remove('on'); $('#hint').style.display = '';
    $$('.nav button').forEach((b) => b.classList.remove('active'));
    render();
  }
  function select(name) {
    ST.sel = name; render(); openPanel('junction', name);
  }
  function rerank() {
    ST.J = recompute(ST.data.junctions, ST.weights); renderMap();
    if (ST.panel === 'priorities') $('#pbody').innerHTML = renderPriorities();
    else if (ST.panel === 'deploy') updateDeploy();
    else if (ST.panel === 'forecast') $('#pbody').innerHTML = renderForecastBody();
    else if (ST.panel === 'adjust') updateWPreview();
    else if (ST.panel === 'junction' && ST.sel) $('#pbody').innerHTML = renderJunction(ST.sel);
  }

  function wire() {
    $$('.nav button').forEach((b) => b.addEventListener('click', () => {
      const p = b.dataset.panel; if (ST.panel === p) closePanel(); else openPanel(p);
    }));
    $('#pclose').addEventListener('click', closePanel);
    $('#scrim').addEventListener('click', closePanel);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && ST.panel) closePanel(); });
    $('#pbody').addEventListener('click', (e) => {
      const q = e.target.closest('.qrow,.riser'); if (q) select(q.dataset.name);
    });
    $('#pbody').addEventListener('keydown', (e) => {
      const q = e.target.closest('.qrow,.riser'); if (q && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); select(q.dataset.name); }
    });
  }

  function wireMap() {                          // zoom (wheel/pinch/buttons/dblclick) + pan (drag)
    const map = $('#map');
    map.addEventListener('wheel', (e) => { e.preventDefault(); const r = map.getBoundingClientRect();
      zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1.18 : 1 / 1.18); }, { passive: false });
    map.addEventListener('dblclick', (e) => { const r = map.getBoundingClientRect();
      zoomAt(e.clientX - r.left, e.clientY - r.top, 1.6); });
    const P = new Map(); let pinch = null;
    map.addEventListener('pointerdown', (e) => {
      if (e.target.closest('.node')) return;     // taps on a dot select it, don't pan
      P.set(e.pointerId, { x: e.clientX, y: e.clientY });
      try { map.setPointerCapture(e.pointerId); } catch (_) { /* ignore */ }
      if (P.size === 2) { const [a, b] = [...P.values()]; pinch = { d: Math.hypot(a.x - b.x, a.y - b.y) }; }
      map.classList.add('grab');
    });
    map.addEventListener('pointermove', (e) => {
      if (!P.has(e.pointerId)) return;
      const prev = P.get(e.pointerId), dx = e.clientX - prev.x, dy = e.clientY - prev.y;
      P.set(e.pointerId, { x: e.clientX, y: e.clientY });
      const r = map.getBoundingClientRect();
      if (P.size >= 2 && pinch) { const [a, b] = [...P.values()], nd = Math.hypot(a.x - b.x, a.y - b.y);
        if (pinch.d > 0) zoomAt((a.x + b.x) / 2 - r.left, (a.y + b.y) / 2 - r.top, nd / pinch.d); pinch.d = nd;
      } else if (P.size === 1) { cam.tx += dx; cam.ty += dy; clampCam(); render(); }
    });
    const up = (e) => { P.delete(e.pointerId); if (P.size < 2) pinch = null; if (!P.size) map.classList.remove('grab'); };
    map.addEventListener('pointerup', up); map.addEventListener('pointercancel', up);
    $('#zin').addEventListener('click', () => zoomAt(mapW / 2, mapH / 2, 1.5));
    $('#zout').addEventListener('click', () => zoomAt(mapW / 2, mapH / 2, 1 / 1.5));
    $('#zreset').addEventListener('click', () => { cam.s = 1; cam.tx = 0; cam.ty = 0; render(); });
    let rt; addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { buildBaseLayers(); render(); }, 150); });
  }

  // ---- init ----
  load().then((data) => {
    ST.data = data; ST.weights = { ...data.meta.weights };
    ST.J = recompute(data.junctions, ST.weights);
    buildBaseLayers(); createNodes(); render(); wire(); wireMap();
    openPanel('brief');   // open with the hook; close it for a clean map
    // tiny read-only handle for automated tests (harmless in production)
    window.__pravah = { cam, ST, draw: () => { drawWorld(); positionNodes(); } };
  });
})();
