// Fills the pick lists and the player analysis from players.js (written by analysis/report.py), and draws the two charts.
(() => {
  const D = window.RR;
  const $ = s => document.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  const ord = n => n + ((n % 100 > 10 && n % 100 < 14) ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' })[n % 10] || 'th');
  const role = tag => tag.split(' · ')[0];
  const signed = v => (v > 0 ? '+' : '') + v;

  function lists() {
    for (const r of ['bat', 'bowl']) {
      $('#picks-' + r).innerHTML = D[r].map((p, i) =>
        `<li><a class="pick" href="#players" data-pick="${r}-${i}"><span class="pick__rank">${p.rank}</span>` +
        `<span class="pick__name">${esc(p.name)}</span><span class="pick__role">${esc(role(p.tag))}</span><span class="pick__elo">${p.elo}</span></a></li>`).join('');
      $('#list-' + r).innerHTML = D[r].map((p, i) =>
        `<li><button class="pl-item" type="button" data-pick="${r}-${i}" aria-pressed="false" aria-controls="pl-open">` +
        `<span class="pl-item__rank">${p.rank}</span><span class="pl-item__name">${esc(p.name)}<small>${esc(role(p.tag))}</small></span>` +
        `<span class="pl-item__elo">${p.elo}</span></button></li>`).join('');
    }
  }

  function picker() {
    // phones choose from one select in place of the 20-row list (the list pane is hidden there)
    $('#pl-select').innerHTML = ['bat', 'bowl'].map(r => `<optgroup label="${r === 'bat' ? 'Batters' : 'Bowlers'}">` +
      D[r].map((p, i) => `<option value="${r}-${i}">${p.rank}. ${esc(p.name)}</option>`).join('') + '</optgroup>').join('');
    $('#pl-select').addEventListener('change', e => open(e.target.value));
  }

  function years(ys) {
    // the zero line sits where the data needs it: near the foot when every year is positive
    const W = 320, H = 184, pad = 16, T = 24, B = 48, up = Math.max(0, ...ys.map(y => y[2])), down = Math.max(0, ...ys.map(y => -y[2]));
    const span = Math.max(20, up + down), plot = H - T - B, mid = T + up / span * plot, scale = plot / span;
    const step = (W - 2 * pad) / ys.length, bw = Math.min(36, step * 0.55);
    const bars = ys.map(([y, n, v], i) => {
      const h = Math.max(1, Math.abs(v) * scale), x = pad + i * step + (step - bw) / 2, cx = x + bw / 2;
      return `<rect x="${x}" y="${v >= 0 ? mid - h : mid}" width="${bw}" height="${h}" rx="3" class="${v >= 0 ? 'up' : 'down'}"/>` +
        `<text class="val" x="${cx}" y="${v >= 0 ? mid - h - 6 : mid + h + 16}">${signed(v)}</text><text x="${cx}" y="${H - 4}">${y}</text>`;
    }).join('');
    const label = ys.map(([y, n, v]) => `${y}: ${signed(v)} over ${n} balls`).join(', ');
    return `<svg class="pl-years" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}"><line class="zero" x1="${pad}" x2="${W - pad}" y1="${mid}" y2="${mid}"/>${bars}</svg>`;
  }

  function open(key) {
    const [r, i] = key.split('-'), p = D[r][+i], who = r === 'bat' ? 'batter' : 'bowler';
    document.querySelectorAll('.pl-item').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pick === key)));
    $('#pl-select').value = key;
    const meter = rank => rank == null ? '' : `<span class="meter" style="--v:${(1 - (rank - 1) / (p.pool - 1)).toFixed(3)}"></span>`;
    const figs = p.figures.map(([k, a, b, rank]) =>
      `<tr><td>${esc(k)}</td><td class="num">${a}</td><td class="num muted">${b}</td>` +
      `<td><span class="meter-cell">${meter(rank)}<span class="num">${rank == null ? '-' : ord(rank)}</span></span></td></tr>`).join('');
    const splits = p.splits.map(([k, n, v]) => `<tr><td>${esc(k)}</td><td class="num">${n}</td><td class="num">${v}</td></tr>`).join('');
    $('#pl-open').innerHTML = `
      <div class="pl-head">
        <p class="t-label muted">${r === 'bat' ? 'Batter' : 'Bowler'} ${p.rank} of my 10 · ${esc(p.tag)}</p>
        <h3>${esc(p.name)}</h3>
        <dl class="pl-stats">
          <div><dt>Pressure Elo</dt><dd>${p.elo}</dd></div><div><dt>Normal Elo</dt><dd>${p.normalElo}</dd></div>
          <div><dt>Pressure matches</dt><dd>${p.matches}</dd></div><div><dt>Good matches</dt><dd>${p.good}%</dd></div>
        </dl>
      </div>
      <p class="pl-note">${esc(p.note)}</p>
      <h4>Under pressure against normal, and his rank among all ${p.pool} qualified ${who}s</h4>
      <table class="pl-table"><thead><tr><th>Figure</th><th>Pressure</th><th>Normal</th><th>Rank of ${p.pool}</th></tr></thead><tbody>${figs}</tbody></table>
      <div class="pl-two">
        <div><h4>By situation, on pressure balls</h4>
          <table class="pl-table"><thead><tr><th>Situation</th><th>Balls</th><th>${esc(p.unit)}</th></tr></thead><tbody>${splits}</tbody></table></div>
        <div><h4>By year, ${esc(p.measure)} per 100 pressure balls</h4>${years(p.years)}</div>
      </div>
      <dl class="pl-foot"><div><dt>Best pressure match</dt><dd>${esc(p.best)}.</dd></div><div><dt>Place in the order</dt><dd>${esc(p.order)}.</dd></div></dl>`;
  }

  // each chart is drawn at its frame's own pixel size, so it fills the frame and its text stays 13px
  const size = el => { el.innerHTML = ''; return [Math.max(280, Math.round(el.clientWidth)), Math.max(280, Math.round(el.clientHeight))]; };

  function byOver(el) {
    const { first, chase } = D.byOver, [W, H] = size(el), L = 40, R = 24, T = 8, B = 28;
    const x = i => L + i * (W - L - R) / 19, y = v => T + (100 - v) / 100 * (H - T - B);
    const line = a => a.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join('');
    const grid = [0, 25, 50, 75, 100].map(v => `<line class="grid-l" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}%</text>`).join('');
    const ticks = [1, 5, 10, 15, 20].map(o => `<text x="${x(o - 1)}" y="${H - 6}" text-anchor="middle">${W < 400 ? o : 'Over ' + o}</text>`).join('');
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true">${grid}${ticks}<path class="ln ln--b" d="${line(first)}"/><path class="ln ln--a" d="${line(chase)}"/></svg>`;
  }

  function rr(el) {
    const { phases, rr: mine, league } = D.rr, [W, H] = size(el), L = 96, R = 48, max = 12, row = H / phases.length, bh = 28;
    const w = v => v / max * (W - L - R);
    const g = phases.map((ph, i) => {
      const y0 = i * row + (row - 2 * bh - 8) / 2;
      return `<text x="0" y="${y0 + bh + 8}">${ph}</text>` +
        `<rect class="bar--a" x="${L}" y="${y0}" width="${w(mine[i])}" height="${bh}" rx="3"/><text class="val" x="${L + w(mine[i]) + 8}" y="${y0 + 19}">${mine[i].toFixed(1)}</text>` +
        `<rect class="bar--b" x="${L}" y="${y0 + bh + 8}" width="${w(league[i])}" height="${bh}" rx="3"/><text x="${L + w(league[i]) + 8}" y="${y0 + bh + 27}">${league[i].toFixed(1)}</text>`;
    }).join('');
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true">${g}</svg>`;
  }

  function cut(el) {
    // ranks 1 to 12 of each list on one Elo axis per list; the dashed line is my top-10 cut
    const [W, h] = size(el), rows = 12, gap = 32, H = Math.max(h, gap + 48 + 2 * rows * 20);  // 20px a row at least
    const L = Math.min(216, Math.round(W * 0.62)), R = 16, rh = (H - gap - 2 * 24) / (2 * rows);
    const block = (list, y0, title) => {
      const lo = Math.floor(Math.min(...list.map(p => p[1])) - 1), hi = Math.ceil(Math.max(...list.map(p => p[1])) + 1);
      const x = v => L + (v - lo) / (hi - lo) * (W - L - R), cy = i => y0 + 24 + (i + 0.5) * rh;
      const dots = list.map(([name, elo], i) =>
        `<text x="0" y="${cy(i) + 4}">${i + 1}. ${esc(name)}</text>` +
        `<line class="grid-l" x1="${L}" x2="${W - R}" y1="${cy(i)}" y2="${cy(i)}"/>` +
        `<circle cx="${x(elo).toFixed(1)}" cy="${cy(i)}" r="5" class="${i < 10 ? 'bar--a' : 'bar--b'}"/>`).join('');
      const cutY = y0 + 24 + 10 * rh;
      return `<text class="val" x="0" y="${y0 + 14}">${title}</text><text x="${W - R}" y="${y0 + 14}" text-anchor="end">${lo} to ${hi} Elo</text>${dots}` +
        `<line x1="0" x2="${W - R}" y1="${cutY}" y2="${cutY}" stroke="currentColor" stroke-dasharray="4 4" class="cutline"/>`;
    };
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true">${block(D.cut.bat, 0, 'Batters')}${block(D.cut.bowl, H / 2 + gap / 2 - 8, 'Bowlers')}</svg>`;
  }

  const charts = () => { byOver($('[data-chart="by-over"]')); rr($('[data-chart="rr"]')); cut($('[data-chart="cut"]')); };
  lists();
  picker();
  charts();
  open('bat-0');
  let wait;
  addEventListener('resize', () => { clearTimeout(wait); wait = setTimeout(charts, 150); });
  document.addEventListener('click', e => {
    const t = e.target.closest('[data-pick]');
    if (t) open(t.dataset.pick);
  });
})();
