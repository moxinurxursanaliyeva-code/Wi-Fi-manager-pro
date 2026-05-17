'use strict';

// ── MOCK DATA ──────────────────────────────────────────────────────────────
const NETS = [
  { ssid:'HomeNetwork_5G',  bssid:'A4:2B:8C:1D:4E:FF', signal:92, auth:'WPA3', cipher:'CCMP', channel:'36', band:'802.11ax / 5 GHz',  connected:true  },
  { ssid:'OfficeWifi',      bssid:'BC:97:E1:03:AB:22', signal:78, auth:'WPA2', cipher:'CCMP', channel:'6',  band:'802.11n / 2.4 GHz', connected:false },
  { ssid:'Neighbor_Net',    bssid:'D8:07:B6:88:CC:11', signal:55, auth:'WPA2', cipher:'TKIP', channel:'11', band:'802.11n / 2.4 GHz', connected:false },
  { ssid:'CoffeeShop_Free', bssid:'F0:18:98:3C:7D:44', signal:41, auth:'Open', cipher:'None', channel:'1',  band:'802.11g / 2.4 GHz', connected:false },
  { ssid:'AndroidAP_5544',  bssid:'22:FD:AB:11:2C:88', signal:28, auth:'WPA2', cipher:'CCMP', channel:'44', band:'802.11ac / 5 GHz', connected:false },
  { ssid:'<Скрытая>',       bssid:'99:AA:BB:CC:DD:EE', signal:15, auth:'WPA2', cipher:'CCMP', channel:'13', band:'802.11n / 2.4 GHz', connected:false },
];

const PROFS = [
  { name:'HomeNetwork_5G',  auth:'WPA3', connected:true,  pass:'SuperSecure#2024' },
  { name:'OfficeWifi',      auth:'WPA2', connected:false, pass:'Office@Pass123'   },
  { name:'CoffeeShop_Free', auth:'Open', connected:false, pass:null               },
  { name:'GrandmaHouse',    auth:'WPA2', connected:false, pass:'qwerty12345'      },
];

const IP_INFO = {
  IPv4: '192.168.1.42', Маска: '255.255.255.0',
  Шлюз: '192.168.1.1',  DNS: '8.8.8.8',
  SSID: 'HomeNetwork_5G', Стандарт: '802.11ax (Wi-Fi 6)',
};

// ── STATE ──────────────────────────────────────────────────────────────────
let state = {
  tab: 'home',
  nets: NETS.map(n => ({...n})),
  profs: PROFS.map(p => ({...p})),
  selectedNet: null,
  selectedProf: null,
  showPass: {},
  scanning: false,
  monRunning: false,
  sigHistory: [72,75,80,84,88,85,82,86,89,92,90,88,85,82,86,90,92,89,85,82],
  sigLog: [],
  pingLines: [],
  pinging: false,
  netSearch: '',
  aiResult: '',
  aiLoading: false,
  connResult: null,
  monInterval: null,
};

// ── UTILS ──────────────────────────────────────────────────────────────────
const sigColor = s => s >= 60 ? 'var(--accent2)' : s >= 30 ? 'var(--warn)' : 'var(--danger)';
const sigColorHex = s => s >= 60 ? '#00e5a0' : s >= 30 ? '#ffaa44' : '#ff5566';

function sigBars(s, size = 14) {
  const f = s >= 80 ? 4 : s >= 60 ? 3 : s >= 40 ? 2 : s >= 20 ? 1 : 0;
  const c = sigColorHex(s);
  let h = `<div class="bars-sm">`;
  for (let i = 1; i <= 4; i++) {
    const ht = Math.round(size * 0.35 + size * 0.18 * i);
    h += `<div class="bar-sm" style="height:${ht}px;background:${i <= f ? c : 'var(--border2)'}"></div>`;
  }
  return h + `</div>`;
}

function sigBarsBig(s) {
  const f = s >= 80 ? 4 : s >= 60 ? 3 : s >= 40 ? 2 : s >= 20 ? 1 : 0;
  const c = sigColorHex(s);
  let h = `<div class="signal-bars-big">`;
  for (let i = 1; i <= 4; i++) {
    const ht = 10 + 10 * i;
    h += `<div class="bar-big" style="height:${ht}px;background:${i <= f ? c : 'var(--border2)'}"></div>`;
  }
  return h + `</div>`;
}

function authBadge(auth) {
  const cls = auth === 'WPA3' ? 'badge-wpa3' : auth === 'WPA2' ? 'badge-wpa2' : 'badge-open';
  return `<span class="badge ${cls}">${auth}</span>`;
}

function showToast(msg, dur = 2200) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), dur);
}

function copyText(txt, msg = '📋 Скопировано') {
  navigator.clipboard?.writeText(txt).catch(() => {});
  showToast(msg);
}

function $(id) { return document.getElementById(id); }

// ── TAB SWITCHING ──────────────────────────────────────────────────────────
function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  render();
}

// ── MAIN RENDER ────────────────────────────────────────────────────────────
function render() {
  const c = document.getElementById('content');
  const fns = { home: renderHome, nets: renderNets, mon: renderMon, prof: renderProf, diag: renderDiag };
  c.innerHTML = (fns[state.tab] || renderHome)();
  postRender();
}

function postRender() {
  if (state.tab === 'mon') setTimeout(drawGraph, 60);
  if (state.tab === 'diag') renderPingLog();
  if (state.tab === 'home' && state.aiResult) {
    const b = $('aiBox');
    if (b) { b.classList.add('visible'); b.textContent = state.aiResult; }
  }
}

// ── HOME TAB ───────────────────────────────────────────────────────────────
function renderHome() {
  const cur = state.nets.find(n => n.connected) || state.nets[0];
  const sc = sigColor(cur.signal);

  return `<div class="section">
    <div class="conn-card">
      <div class="conn-card-status">
        <div class="conn-dot"></div>
        <span class="status-badge">● ПОДКЛЮЧЕНО</span>
      </div>
      <div class="conn-ssid">${cur.ssid}</div>
      <div class="conn-bssid">${cur.bssid}</div>
      <div class="conn-metrics">
        <div>
          <div class="conn-signal-big" style="color:${sc}">${cur.signal}%</div>
          <div class="conn-signal-lbl">сигнал</div>
        </div>
        ${sigBarsBig(cur.signal)}
        <div class="conn-info-grid">
          <div>
            <div class="conn-info-item-label">безопасность</div>
            <div class="conn-info-item-val" style="color:${sc}">${cur.auth}</div>
          </div>
          <div>
            <div class="conn-info-item-label">диапазон</div>
            <div class="conn-info-item-val">${cur.band.split('/')[1]?.trim() || '5 GHz'}</div>
          </div>
          <div>
            <div class="conn-info-item-label">канал</div>
            <div class="conn-info-item-val">${cur.channel}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="ip-grid">
      ${[['💻','192.168.1.42','IPv4'],['🌐','192.168.1.1','шлюз'],['🔍','8.8.8.8','DNS'],['📡','CH ${cur.channel}','канал']].map(([ic,v,l])=>`
      <div class="ip-cell">
        <span class="ip-cell-icon">${ic}</span>
        <div class="ip-cell-val">${v}</div>
        <div class="ip-cell-lbl">${l}</div>
      </div>`).join('')}
    </div>

    <div class="card">
      <div class="card-head"><span>🤖</span> AI-АНАЛИЗ СЕТИ</div>
      <button class="btn btn-primary" onclick="runAI()" id="aiBtn" ${state.aiLoading ? 'disabled' : ''}>
        <span class="btn-icon">${state.aiLoading ? '⏳' : '✨'}</span>
        ${state.aiLoading ? 'Анализирую...' : state.aiResult ? 'Анализировать снова' : 'Проанализировать сеть'}
      </button>
      <div class="ai-result ${state.aiResult || state.aiLoading ? 'visible' : ''}" id="aiBox">
        ${state.aiLoading ? '<span class="ai-thinking">Claude анализирует параметры сети...</span>' : (state.aiResult || '')}
      </div>
    </div>

    <div class="card">
      <div class="card-head"><span>⚡</span> БЫСТРЫЕ ДЕЙСТВИЯ</div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <button class="btn btn-outline" onclick="quickPing()">
          <span class="btn-icon">📶</span>Пинг шлюза (192.168.1.1)
        </button>
        <button class="btn btn-outline" onclick="switchTab('nets')">
          <span class="btn-icon">🔄</span>Сканировать сети
        </button>
        <button class="btn btn-outline" onclick="copyText('192.168.1.42','📋 IP скопирован')">
          <span class="btn-icon">📋</span>Копировать IP
        </button>
        <button class="btn btn-outline" onclick="switchTab('diag')">
          <span class="btn-icon">🛠</span>Открыть диагностику
        </button>
      </div>
    </div>
  </div>`;
}

// ── AI ANALYSIS ────────────────────────────────────────────────────────────
async function runAI() {
  const cur = state.nets.find(n => n.connected) || state.nets[0];
  state.aiLoading = true;
  state.aiResult = '';
  render();

  const prompt = `Ты — эксперт по Wi-Fi сетям. Проанализируй сеть и дай краткий, конкретный совет на русском (3-5 предложений):

SSID: ${cur.ssid}
Сигнал: ${cur.signal}%
Безопасность: ${cur.auth} / ${cur.cipher}
Канал: ${cur.channel}, Диапазон: ${cur.band}
IP: 192.168.1.42, Шлюз: 192.168.1.1, DNS: 8.8.8.8

Оцени: качество сигнала, безопасность, диапазон. Дай 1-2 конкретных совета.`;

  try {
    const resp = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'claude-sonnet-4-20250514',
        max_tokens: 1000,
        messages: [{ role: 'user', content: prompt }]
      })
    });
    const data = await resp.json();
    state.aiResult = data.content?.find(b => b.type === 'text')?.text || 'Не удалось получить ответ.';
  } catch (e) {
    state.aiResult = '⚠️ Ошибка подключения к Claude API.\n\nПриложение работает в демо-режиме. Для активации AI-анализа разверните бэкенд с API-ключом.';
  }

  state.aiLoading = false;
  render();
}

// ── NETS TAB ───────────────────────────────────────────────────────────────
function renderNets() {
  const q = state.netSearch.toLowerCase();
  const filtered = state.nets
    .filter(n => !q || n.ssid.toLowerCase().includes(q) || n.bssid.toLowerCase().includes(q))
    .sort((a, b) => b.signal - a.signal);

  return `<div class="section">
    <div class="search-row">
      <div class="input-wrap" style="flex:1">
        <span class="input-icon">🔍</span>
        <input type="text" placeholder="Поиск сети..."
          value="${state.netSearch}"
          oninput="state.netSearch=this.value; renderNetsOnly()">
      </div>
      <button class="btn btn-outline" style="width:auto;padding:12px 14px;white-space:nowrap"
        onclick="scanNets()" id="scanBtn" ${state.scanning ? 'disabled' : ''}>
        <span ${state.scanning ? 'class="spinning"' : ''}>🔄</span>
        ${state.scanning ? '' : 'Обновить'}
      </button>
    </div>

    <div class="count-badge">Найдено: ${filtered.length} / ${state.nets.length} сетей</div>

    <div class="net-list" id="netList">
      ${filtered.map(n => renderNetRow(n)).join('')}
    </div>
  </div>`;
}

function renderNetRow(n) {
  const isOpen = state.selectedNet === n.bssid;
  const sc = sigColor(n.signal);
  return `<div class="net-row ${isOpen ? 'open' : ''}" onclick="toggleNet('${n.bssid}')">
    <div class="net-row-top">
      <div>
        <div class="net-name" style="color:${n.connected ? 'var(--accent2)' : 'var(--text)'}">${n.ssid}</div>
      </div>
      <div class="net-sig-wrap">
        ${sigBars(n.signal)}
        <span class="net-sig-pct" style="color:${sc}">${n.signal}%</span>
      </div>
    </div>
    <div class="net-meta">
      ${authBadge(n.auth)}
      ${n.connected ? '<span class="badge badge-conn">● активна</span>' : ''}
      <span class="badge badge-ch">CH ${n.channel}</span>
      <span class="badge badge-ch">${n.band.split('/')[1]?.trim() || n.band}</span>
    </div>
    <div class="net-detail ${isOpen ? 'open' : ''}">
      <div class="net-detail-inner">
        <div class="kv-row"><span class="kv-key">BSSID</span><span class="kv-val" style="font-size:11px">${n.bssid}</span></div>
        <div class="kv-row"><span class="kv-key">Шифрование</span><span class="kv-val">${n.cipher}</span></div>
        <div class="kv-row"><span class="kv-key">Диапазон</span><span class="kv-val">${n.band}</span></div>
        <div class="kv-row"><span class="kv-key">Канал</span><span class="kv-val">${n.channel}</span></div>
        <div class="net-actions">
          <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); connectToNet('${n.ssid}','${n.auth}')">
            🔗 Подключить
          </button>
          <button class="btn btn-outline btn-sm net-actions btn-icon-only" onclick="event.stopPropagation(); copyText('${n.ssid}','📋 SSID скопирован')">
            📋
          </button>
          <button class="btn btn-outline btn-sm net-actions btn-icon-only" onclick="event.stopPropagation(); copyText('${n.bssid}','📋 BSSID скопирован')">
            🔖
          </button>
        </div>
      </div>
    </div>
  </div>`;
}

function toggleNet(bssid) {
  state.selectedNet = state.selectedNet === bssid ? null : bssid;
  const list = $('netList');
  if (list) {
    const filtered = state.nets
      .filter(n => !state.netSearch || n.ssid.toLowerCase().includes(state.netSearch.toLowerCase()))
      .sort((a, b) => b.signal - a.signal);
    list.innerHTML = filtered.map(n => renderNetRow(n)).join('');
  }
}

function renderNetsOnly() {
  const list = $('netList');
  if (!list) return;
  const filtered = state.nets
    .filter(n => !state.netSearch || n.ssid.toLowerCase().includes(state.netSearch.toLowerCase()))
    .sort((a, b) => b.signal - a.signal);
  list.innerHTML = filtered.map(n => renderNetRow(n)).join('');
  const cnt = document.querySelector('.count-badge');
  if (cnt) cnt.textContent = `Найдено: ${filtered.length} / ${state.nets.length} сетей`;
}

function scanNets() {
  state.scanning = true;
  render();
  setTimeout(() => {
    state.nets = NETS.map(n => ({
      ...n,
      signal: Math.max(10, Math.min(99, n.signal + Math.floor(Math.random() * 12) - 6))
    }));
    state.scanning = false;
    render();
    showToast('✅ Сканирование завершено');
  }, 1800);
}

function connectToNet(ssid, auth) {
  const msg = auth === 'Open'
    ? `✅ Подключение к «${ssid}» без пароля...`
    : `🔗 Переходим к подключению к «${ssid}»`;
  showToast(msg, 2500);
}

// ── MONITOR TAB ────────────────────────────────────────────────────────────
function renderMon() {
  const h = state.sigHistory;
  const avg = h.length ? Math.round(h.reduce((a, b) => a + b) / h.length) : 0;
  const mn  = h.length ? Math.min(...h) : 0;
  const mx  = h.length ? Math.max(...h) : 0;

  return `<div class="section">
    <div class="mon-stats-row">
      <div class="mon-stat">
        <div class="mon-stat-val" style="color:var(--accent)">${avg}%</div>
        <div class="mon-stat-lbl">AVG</div>
      </div>
      <div class="mon-stat">
        <div class="mon-stat-val" style="color:var(--warn)">${mn}%</div>
        <div class="mon-stat-lbl">MIN</div>
      </div>
      <div class="mon-stat">
        <div class="mon-stat-val" style="color:var(--accent2)">${mx}%</div>
        <div class="mon-stat-lbl">MAX</div>
      </div>
    </div>

    <div class="graph-wrap">
      <div class="card-head" style="margin-bottom:10px"><span>📊</span> ГРАФИК СИГНАЛА (${h.length} точек)</div>
      <canvas id="sigCanvas" height="120"></canvas>
    </div>

    <div class="flex-row mt12">
      <button class="btn ${state.monRunning ? 'btn-danger' : 'btn-green'}" onclick="toggleMon()" id="monBtn">
        ${state.monRunning ? '⏹ Остановить' : '▶ Запустить мониторинг'}
      </button>
      <button class="btn btn-outline" style="flex:none;width:48px" onclick="clearMon()">🗑</button>
    </div>

    ${state.sigLog.length ? `
    <div class="log-box" id="logBox">
      ${state.sigLog.slice(0, 50).map((l, i) => `<div class="${i === 0 ? 'log-new' : 'log-old'}">${l}</div>`).join('')}
    </div>` : ''}
  </div>`;
}

function drawGraph() {
  const canvas = $('sigCanvas');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.offsetWidth || 340;
  const H = 120;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  ctx.fillStyle = '#0a0a0f';
  ctx.fillRect(0, 0, W, H);

  const pad = 8, pl = 30;

  [25, 50, 75, 100].forEach(pct => {
    const y = H - pad - (H - 2 * pad) * pct / 100;
    ctx.strokeStyle = '#2a2a3d';
    ctx.setLineDash([4, 6]);
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pl, y); ctx.lineTo(W - pad, y); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#4a4a70';
    ctx.font = '9px monospace';
    ctx.fillText(pct + '%', 2, y + 4);
  });

  const h = state.sigHistory;
  if (h.length < 2) return;

  const xs = h.map((_, i) => pl + (W - pl - pad) * i / (h.length - 1));
  const ys = h.map(v => H - pad - (H - 2 * pad) * v / 100);

  // area fill
  ctx.beginPath();
  ctx.moveTo(xs[0], H - pad);
  for (let i = 0; i < xs.length; i++) {
    if (i === 0) ctx.lineTo(xs[i], ys[i]);
    else {
      const cpx = (xs[i - 1] + xs[i]) / 2;
      ctx.bezierCurveTo(cpx, ys[i - 1], cpx, ys[i], xs[i], ys[i]);
    }
  }
  ctx.lineTo(xs[xs.length - 1], H - pad);
  ctx.closePath();
  ctx.fillStyle = 'rgba(79,158,255,0.12)';
  ctx.fill();

  // line
  ctx.beginPath();
  ctx.moveTo(xs[0], ys[0]);
  for (let i = 1; i < xs.length; i++) {
    const cpx = (xs[i - 1] + xs[i]) / 2;
    ctx.bezierCurveTo(cpx, ys[i - 1], cpx, ys[i], xs[i], ys[i]);
  }
  ctx.strokeStyle = '#4f9eff';
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // endpoint dot
  const lx = xs[xs.length - 1], ly = ys[ys.length - 1];
  ctx.beginPath();
  ctx.arc(lx, ly, 5, 0, Math.PI * 2);
  ctx.fillStyle = '#4f9eff';
  ctx.fill();
  ctx.strokeStyle = '#0a0a0f';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = '#4f9eff';
  ctx.font = 'bold 10px monospace';
  ctx.fillText(h[h.length - 1] + '%', lx + 8, ly + 4);
}

function toggleMon() {
  state.monRunning = !state.monRunning;
  if (state.monRunning) {
    state.monInterval = setInterval(() => {
      const last = state.sigHistory[state.sigHistory.length - 1] || 85;
      const nv = Math.max(15, Math.min(99, last + Math.floor(Math.random() * 14) - 7));
      state.sigHistory.push(nv);
      if (state.sigHistory.length > 60) state.sigHistory.shift();
      const ts = new Date().toLocaleTimeString('ru-RU');
      state.sigLog.unshift(`[${ts}]  HomeNetwork_5G   ${nv}%  ${nv >= 60 ? '✅' : nv >= 30 ? '⚠️' : '❌'}`);
      if (state.sigLog.length > 60) state.sigLog.pop();
      if (state.tab === 'mon') render();
    }, 2000);
  } else {
    clearInterval(state.monInterval);
  }
  render();
}

function clearMon() {
  state.sigHistory = [];
  state.sigLog = [];
  render();
}

// ── PROFILES TAB ───────────────────────────────────────────────────────────
function renderProf() {
  return `<div class="section">
    <div class="count-badge">Сохранено профилей: ${state.profs.length}</div>
    ${state.profs.map(p => renderProfRow(p)).join('')}
  </div>`;
}

function renderProfRow(p) {
  const isOpen = state.selectedProf === p.name;
  const sp = state.showPass[p.name];
  const avatarBg = p.connected ? 'rgba(0,229,160,.12)' : p.auth === 'Open' ? 'rgba(255,170,68,.12)' : 'rgba(79,158,255,.12)';
  const avatarColor = p.connected ? 'var(--accent2)' : p.auth === 'Open' ? 'var(--warn)' : 'var(--accent)';
  const icon = p.connected ? '📶' : p.auth === 'Open' ? '🔓' : '🔒';

  return `<div class="prof-row ${isOpen ? 'open' : ''}" onclick="toggleProf('${p.name}')">
    <div class="prof-top">
      <div class="prof-avatar" style="background:${avatarBg};color:${avatarColor}">
        ${icon}
      </div>
      <div>
        <div class="prof-name" style="color:${p.connected ? 'var(--accent2)' : 'var(--text)'}">${p.name}</div>
        <div class="prof-auth">${p.auth} ${p.connected ? '· <span style="color:var(--accent2)">активна</span>' : ''}</div>
      </div>
      <span class="prof-chevron">⌄</span>
    </div>

    <div class="prof-detail ${isOpen ? 'open' : ''}">
      <div class="prof-detail-inner">
        ${p.pass ? `
        <div class="pass-box">
          <div class="pass-lbl">🔑 ПАРОЛЬ</div>
          <div class="pass-val ${sp ? 'revealed' : ''}" id="pv-${p.name}">
            ${sp ? p.pass : '●'.repeat(p.pass.length)}
          </div>
        </div>
        <div class="pass-actions mt8">
          <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); togglePass('${p.name}')">
            ${sp ? '🙈 Скрыть' : '👁 Показать'}
          </button>
          <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); copyText('${p.pass}','🔑 Пароль скопирован')">
            📋 Копировать
          </button>
        </div>` :
        `<div class="text-sub">Открытая сеть — пароль не требуется</div>`}

        ${!p.connected ? `
        <button class="btn btn-primary btn-sm mt8" onclick="event.stopPropagation(); showToast('🔗 Подключение к ${p.name}...')">
          🔗 Подключиться
        </button>` : ''}

        <button class="btn btn-outline btn-sm mt8" style="color:var(--danger);border-color:rgba(255,85,102,.3)"
          onclick="event.stopPropagation(); deleteProf('${p.name}')">
          🗑 Удалить профиль
        </button>
      </div>
    </div>
  </div>`;
}

function toggleProf(name) {
  state.selectedProf = state.selectedProf === name ? null : name;
  render();
}

function togglePass(name) {
  state.showPass[name] = !state.showPass[name];
  const el = $('pv-' + name);
  const p = state.profs.find(x => x.name === name);
  if (el && p) {
    const sp = state.showPass[name];
    el.className = 'pass-val' + (sp ? ' revealed' : '');
    el.textContent = sp ? p.pass : '●'.repeat(p.pass.length);
  }
}

function deleteProf(name) {
  if (!confirm(`Удалить профиль «${name}»?\nСеть будет забыта.`)) return;
  state.profs = state.profs.filter(p => p.name !== name);
  state.selectedProf = null;
  render();
  showToast('🗑 Профиль удалён');
}

// ── DIAGNOSTICS TAB ────────────────────────────────────────────────────────
function renderDiag() {
  return `<div class="section">
    <div class="card">
      <div class="card-head"><span>🌐</span> СЕТЕВАЯ ИНФОРМАЦИЯ</div>
      <div class="diag-table">
        ${Object.entries(IP_INFO).map(([k, v]) => `
        <div class="diag-tr">
          <span class="diag-key">${k}</span>
          <span class="diag-val">${v}</span>
        </div>`).join('')}
      </div>
    </div>

    <div class="card">
      <div class="card-head"><span>⚡</span> БЫСТРЫЕ ДЕЙСТВИЯ</div>
      <div class="quick-grid">
        ${[
          ['🔄','Сброс TCP/IP','var(--warn)',  () => showToast('🔄 Сброс TCP/IP выполнен')],
          ['♻️','Обновить DHCP','var(--accent2)', () => showToast('✅ DHCP обновлён')],
          ['🗑','Очистить DNS', 'var(--accent)',  () => showToast('🗑 DNS-кэш очищен')],
          ['🔌','Откл. Wi-Fi',  'var(--danger)',  () => showToast('⚠️ Требуются права администратора')],
        ].map(([ic, lbl, col]) => `
        <button class="quick-btn" onclick="showToast('${ic} ${lbl}...')" style="color:${col};border-color:${col}33">
          <span class="qb-icon">${ic}</span>${lbl}
        </button>`).join('')}
      </div>
    </div>

    <div class="card">
      <div class="card-head"><span>📡</span> PING / ТРАССИРОВКА</div>
      <div class="flex-row" style="margin-bottom:10px">
        <input type="text" id="pingHost" value="8.8.8.8" placeholder="Хост или IP">
        <button class="btn btn-primary" style="flex:none;width:auto;padding:12px 16px"
          onclick="doPing()" id="pingBtn" ${state.pinging ? 'disabled' : ''}>
          ${state.pinging ? '⏳' : 'Ping'}
        </button>
      </div>
      <div class="flex-row">
        <button class="btn btn-outline btn-sm" onclick="doTrace()">🗺 Tracert</button>
        <button class="btn btn-outline btn-sm" onclick="clearPing()">🗑 Очистить</button>
      </div>
      <div class="ping-log" id="pingLog"></div>
    </div>
  </div>`;
}

function renderPingLog() {
  const el = $('pingLog');
  if (!el || !state.pingLines.length) return;
  el.innerHTML = state.pingLines.map(l => {
    const cls = l.startsWith('──') ? 'ping-info' : l.includes('Запрос') ? 'ping-fail' : l.includes('Статист') ? 'ping-stat' : 'ping-ok';
    return `<div class="${cls}">${l}</div>`;
  }).join('');
}

function doPing() {
  if (state.pinging) return;
  const host = $('pingHost')?.value || '8.8.8.8';
  state.pinging = true;
  state.pingLines.unshift(`── Ping ${host} ──`);
  render();
  let count = 0;
  const t = setInterval(() => {
    const ms = Math.floor(Math.random() * 28) + 4;
    const loss = Math.random() > 0.92;
    state.pingLines.unshift(
      loss ? `Запрос превысил время ожидания.`
           : `Ответ от ${host}: время=${ms} мс TTL=57`
    );
    count++;
    if (count >= 4) {
      clearInterval(t);
      state.pingLines.unshift(`Статистика: мин=${ms - 2} макс=${ms + 8} ср=${ms} мс`);
      state.pinging = false;
      const btn = $('pingBtn');
      if (btn) { btn.disabled = false; btn.textContent = 'Ping'; }
    }
    renderPingLog();
  }, 500);
}

function doTrace() {
  state.pingLines.unshift('── Tracert 8.8.8.8 ──');
  const hops = [
    '1 ms   192.168.1.1   (шлюз)',
    '5 ms   10.0.0.1',
    '8 ms   95.167.0.1',
    '12 ms  209.85.241.74',
    '14 ms  8.8.8.8   ✅',
  ];
  hops.forEach((h, i) => setTimeout(() => {
    state.pingLines.unshift(`${i + 1}   ${h}`);
    renderPingLog();
  }, i * 450));
}

function clearPing() {
  state.pingLines = [];
  renderPingLog();
}

function quickPing() {
  switchTab('diag');
  setTimeout(() => doPing(), 300);
}

// ── PWA INSTALL ────────────────────────────────────────────────────────────
let deferredPrompt = null;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  deferredPrompt = e;
  const banner = $('install-banner');
  if (banner) banner.classList.add('visible');
});

function installApp() {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  deferredPrompt.userChoice.then(r => {
    deferredPrompt = null;
    const banner = $('install-banner');
    if (banner) banner.classList.remove('visible');
    if (r.outcome === 'accepted') showToast('✅ Приложение установлено!');
  });
}

// ── SERVICE WORKER ─────────────────────────────────────────────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  });
}

// ── INIT ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  render();
});
