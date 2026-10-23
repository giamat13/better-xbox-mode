'use strict';
(() => {
const xbox = window.xbox;
const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, cls, html) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html != null) e.innerHTML = html;
  return e;
};
const esc = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const TABS = ['Library', 'Places', 'Running', 'Settings'];
const TAB = { LIB: 0, PLACES: 1, RUN: 2, SET: 3 };
const PLACE_GLYPH = { site: '🌐', folder: '📁', file: '🗎' };
const PLACE_LABEL = { site: 'Favorite site', folder: 'Folder', file: 'Recent file' };
const QUICK_COLS = 4;
const GAME_HINTS = /steam|epic games|gog|ubisoft|ea app|battle\.net|xbox|minecraft|game/i;
const ZONE = { TOP: 0, RECENT: 1, TABS: 2, CARDS: 3 };
const XLOGO = '<svg viewBox="0 0 32 32"><circle cx="16" cy="16" r="14" fill="#107c10" stroke="none"/><circle cx="16" cy="16" r="14" stroke="#eee" stroke-width="1.6"/><path d="M10 10l12 12M22 10L10 22" stroke="#eee" stroke-width="3"/></svg>';
const WINLOGO = '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="3" y="3" width="8" height="8"/><rect x="13" y="3" width="8" height="8"/><rect x="3" y="13" width="8" height="8"/><rect x="13" y="13" width="8" height="8"/></svg>';
const MODES = [{ label: 'Xbox full screen experience', icon: XLOGO }, { label: 'Windows desktop', icon: WINLOGO }];

const S = {
  apps: [], cfg: {}, wins: [], places: [], quick: null, padBattery: null, displayLabel: '', view: 'home', zone: ZONE.RECENT, top: 0, recent: 0, tab: 0, card: 0,
  filter: '', searching: false, help: false, ranked: [], sw: null,
};

// ---- artwork ---------------------------------------------------------------------
const iconCache = new Map();
const hueOf = (name) => [...name].reduce((h, c, i) => (h + c.charCodeAt(0) * (i + 3)) % 360, 0);
const gradient = (hue, sat = 45) =>
  `linear-gradient(155deg, hsl(${hue} ${sat}% 36%), hsl(${hue} ${Math.min(sat, 50)}% 11%))`;

function analyse(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = c.height = 24;
      const g = c.getContext('2d');
      g.drawImage(img, 0, 0, 24, 24);
      const d = g.getImageData(0, 0, 24, 24).data;
      let r = 0, gr = 0, b = 0, w = 0;
      for (let i = 0; i < d.length; i += 4) {
        if (d[i + 3] < 128) continue;
        const sat = Math.max(d[i], d[i + 1], d[i + 2]) - Math.min(d[i], d[i + 1], d[i + 2]);
        const wt = 1 + sat / 24;
        r += d[i] * wt; gr += d[i + 1] * wt; b += d[i + 2] * wt; w += wt;
      }
      if (!w) return resolve(null);
      r /= w; gr /= w; b /= w;
      const mx = Math.max(r, gr, b), mn = Math.min(r, gr, b), dl = mx - mn;
      let h = 0;
      if (dl) {
        if (mx === r) h = ((gr - b) / dl) % 6; else if (mx === gr) h = (b - r) / dl + 2; else h = (r - gr) / dl + 4;
      }
      resolve({ hue: Math.round(((h * 60) + 360) % 360), sat: Math.max(25, Math.min(62, Math.round((dl / (mx || 1)) * 100))) });
    };
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

function iconFor(app) {
  if (!iconCache.has(app.path)) {
    iconCache.set(app.path, xbox.icon(app.path).then(async (url) => {
      if (!url) return null;
      return { url, ...(await analyse(url) || { hue: hueOf(app.name), sat: 40 }) };
    }));
  }
  return iconCache.get(app.path);
}

function paint(app, host, imgParent) {
  host.style.background = gradient(hueOf(app.name));
  iconFor(app).then((info) => {
    if (!info) return;
    app.hue = info.hue;
    host.style.background = gradient(info.hue, info.sat);
    const img = el('img', 'ico');
    img.src = info.url;
    imgParent.prepend(img);
    if (host.dataset.bg === '1') setBackground(app);
  });
}

function setBackground(app) {
  $('#bgArt').style.background = gradient(app.hue ?? hueOf(app.name), 55);
}

// ---- data ------------------------------------------------------------------------
function rank(apps) {
  return [...apps].sort((a, b) => (b.last - a.last)
    || (GAME_HINTS.test(b.name) - GAME_HINTS.test(a.name)) || a.name.localeCompare(b.name));
}

function relTime(secs) {
  if (!secs) return 'Not played yet';
  const days = Math.floor((Date.now() / 1000 - secs) / 86400);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return `${Math.floor(days / 7)} week${days >= 14 ? 's' : ''} ago`;
}

async function loadData() {
  [S.cfg, S.apps, S.places] = await Promise.all([xbox.call('config_get'), xbox.call('apps'), xbox.call('places')]);
  S.ranked = rank(S.apps);
  applySettings();
  xbox.displays().then((list) => { S.displayLabel = (list.find((d) => d.current) || {}).label || ''; });
}

// Settings that act on the interface itself rather than on the engine.
function applySettings() {
  document.body.classList.toggle('nohints', S.cfg.show_hints === false);
  window.sfx.enable(S.cfg.ui_sounds !== false);
}

async function cycleDisplay() {
  const list = await xbox.displays();
  if (list.length < 2) { showModeBanner('One display', 'No other display was found', ''); return; }
  const next = list[(list.findIndex((d) => d.current) + 1) % list.length];
  await xbox.setDisplay(next.id);
  S.displayLabel = next.label;
  showModeBanner('Moved here', next.label, '');
  renderCards();
  updateFocus();
}

// ---- home rendering ------------------------------------------------------------------
function settingsItems() {
  const on = (v) => (v ? 'On' : 'Off');
  return [
    { title: 'Hide taskbar', state: on(S.cfg.hide_taskbar), glyph: '▭', run: () => toggle('hide_taskbar') },
    { title: 'Controller as mouse', state: on(S.cfg.mouse_mode), glyph: '🖱', run: () => toggle('mouse_mode') },
    { title: 'Open apps full screen', state: on(S.cfg.launch_fullscreen), glyph: '⛶', run: () => toggle('launch_fullscreen') },
    { title: 'Run as administrator', state: on(S.cfg.run_as_admin), glyph: '🛡', run: () => toggle('run_as_admin') },
    { title: 'Display', state: S.displayLabel, glyph: '🖥', run: cycleDisplay },
    { title: 'Interface sounds', state: on(S.cfg.ui_sounds !== false), glyph: '🔔', run: () => toggle('ui_sounds', true) },
    { title: 'Button hints', state: on(S.cfg.show_hints !== false), glyph: '🎮', run: () => toggle('show_hints', true) },
    { title: 'Restore hidden apps', state: `${(S.cfg.hidden_apps || []).length}`, glyph: '👁',
      run: async () => {
        await xbox.call('config_set', { key: 'hidden_apps', value: [] });
        await xbox.call('config_set', { key: 'windowless', value: {} });
        await loadData();
        renderHome();
      } },
    { title: 'Rescan apps', state: '', glyph: '⟳', run: async () => { await loadData(); renderHome(); } },
    { title: 'Exit Xbox Mode', state: '', glyph: '⏻', run: () => xbox.quit() },
  ];
}

async function toggle(key, defaultOn = false) {
  S.cfg[key] = !(S.cfg[key] ?? defaultOn);
  await xbox.call('config_set', { key, value: S.cfg[key] });
  applySettings();
  if (S.quick) renderQuick();
  renderCards();
  updateFocus();
}

function filtered() {
  const q = S.filter.trim().toLowerCase();
  return q ? S.ranked.filter((a) => a.name.toLowerCase().includes(q)) : S.ranked;
}

const SHELF = 12;  // the home shelf shows this many apps, then a "See all" card opens the library grid

function cardCount() {
  if (S.tab === TAB.LIB) { const n = filtered().length; return Math.min(n, SHELF) + (n > SHELF ? 1 : 0); }
  if (S.tab === TAB.PLACES) return S.places.length;
  if (S.tab === TAB.RUN) return S.wins.length;
  return settingsItems().length;
}

function renderHome() {
  const row = $('#recentRow');
  row.innerHTML = '';
  S.ranked.slice(0, 3).forEach((app, i) => {
    const t = el('div', `tile ${i === 0 ? 'hero' : 'poster'}`);
    t.dataset.bg = '1';
    t.append(el('div', 'name', esc(app.name)));
    paint(app, t, t);
    row.append(t);
  });
  row.append(el('div', 'tile more', 'View more in<br>your Library'));

  const tabs = $('#tabs');
  tabs.innerHTML = '';
  TABS.forEach((name) => tabs.append(el('div', 'tab', name)));
  renderCards();
  if (S.ranked[0]) setBackground(S.ranked[0]);
  updateFocus();
}

function artCard(label, title, state) {
  const card = el('div', 'card');
  card.append(el('div', 'label', esc(label)));
  const box = el('div', 'box');
  const art = el('div', 'art');
  box.append(art, el('div', 'strip', `<span>${esc(title)}</span>${state ? `<span class="state">${esc(state)}</span>` : ''}`));
  card.append(box);
  return { card, art };
}

function renderCards() {
  const row = $('#cardsRow');
  row.innerHTML = '';
  if (S.tab === TAB.LIB) {
    const apps = filtered();
    if (!apps.length) row.append(el('div', 'empty', S.filter ? 'No apps match your search.' : 'No apps found.'));
    apps.slice(0, SHELF).forEach((app) => {
      const { card, art } = artCard(relTime(app.last), app.name);
      paint(app, art, art);
      row.append(card);
    });
    if (apps.length > SHELF) {
      const { card, art } = artCard('Library', 'See all', `${apps.length}`);
      art.style.background = gradient(215, 30);
      art.append(el('div', 'glyph', '▦'));
      row.append(card);
    }
  } else if (S.tab === TAB.PLACES) {
    if (!S.places.length) row.append(el('div', 'empty', 'No places found.'));
    S.places.forEach((p) => {
      const { card, art } = artCard(PLACE_LABEL[p.kind], p.name);
      art.style.background = gradient(hueOf(p.kind === 'site' ? p.name : p.kind), 30);
      art.append(el('div', 'glyph', PLACE_GLYPH[p.kind]));
      row.append(card);
    });
  } else if (S.tab === TAB.RUN) {
    if (!S.wins.length) row.append(el('div', 'empty', 'Nothing is running.'));
    S.wins.forEach((w) => {
      const { card, art } = artCard('Running', w.title);
      art.style.background = gradient(hueOf(w.title), 30);
      if (w.thumb) {
        const img = el('img', 'shot');
        img.src = w.thumb;
        art.append(img);
      }
      row.append(card);
    });
  } else {
    settingsItems().forEach((it) => {
      const { card, art } = artCard('Setting', it.title, it.state);
      art.style.background = gradient(150, 25);
      art.append(el('div', 'glyph', it.glyph));
      row.append(card);
    });
  }
}

function mergeWindows(wins, thumbs) {
  const byHwnd = new Map(thumbs.map((t) => [t.hwnd, t]));
  return wins.map((w) => ({ ...w, thumb: byHwnd.get(w.hwnd)?.thumb || null, icon: byHwnd.get(w.hwnd)?.icon || null }));
}

async function refreshRunning() {
  const [wins, thumbs] = await Promise.all([xbox.call('windows'), xbox.thumbs({ w: 640, h: 360 })]);
  S.wins = mergeWindows(wins, thumbs);
}

// A window we just asked to close can linger for a moment; keep it out of the lists meanwhile.
const closing = new Map();
function markClosing(hwnd) {
  closing.set(hwnd, Date.now() + 3000);
}

function updateFocus() {
  document.querySelectorAll('.focus').forEach((e) => e.classList.remove('focus'));
  const tabs = $('#tabs').children;
  [...tabs].forEach((t, i) => t.classList.toggle('active', i === S.tab));
  let target = null;
  if (S.zone === ZONE.TOP) target = [$('#searchBtn'), $('#helpBtn')][S.top];
  else if (S.zone === ZONE.RECENT) target = $('#recentRow').children[S.recent];
  else if (S.zone === ZONE.TABS) target = tabs[S.tab];
  else target = $('#cardsRow').children[S.card];
  if (target) {
    target.classList.add('focus');
    if (S.zone === ZONE.CARDS) centerIn($('#cardsWrap'), target, 'x');
  }
  if (S.zone === ZONE.RECENT && S.ranked[S.recent]) setBackground(S.ranked[S.recent]);
  const inCards = S.zone === ZONE.CARDS;
  $('#hintA').textContent = inCards && S.tab === TAB.RUN ? 'SWITCH  ·  X CLOSE'
    : inCards && S.tab === TAB.PLACES ? 'OPEN  ·  X REMOVE SITE' : 'SELECT';
}

// ---- home input -------------------------------------------------------------------------
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// Scrolls only the given container so the element sits in its middle. scrollIntoView also scrolls the page itself,
// which pushed the header and the search box off screen during fast scrolling.
function centerIn(container, element, axis) {
  if (!element) return;
  if (axis === 'x') container.scrollTo({ left: element.offsetLeft - (container.clientWidth - element.offsetWidth) / 2, behavior: 'smooth' });
  else container.scrollTo({ top: element.offsetTop - (container.clientHeight - element.offsetHeight) / 2, behavior: 'smooth' });
}

// The page must never scroll (only the grid and the shelf do); undo it if anything ever pushes it.
document.addEventListener('scroll', () => {
  const root = document.scrollingElement;
  if (root.scrollTop || root.scrollLeft) root.scrollTo(0, 0);
});

async function setTab(i) {
  S.tab = ((i % TABS.length) + TABS.length) % TABS.length;
  S.card = 0;
  if (S.tab === TAB.RUN) await refreshRunning();
  renderCards();
  updateFocus();
}

async function launch(app) {
  await xbox.call('launch', { path: app.path, name: app.name });
  app.last = Date.now() / 1000;
  S.ranked = rank(S.apps);
  // The tiles on screen must follow the new order, or the next press launches whatever now sits at that position.
  if (S.view === 'library') renderLibrary(); else renderHome();
}

async function homeButton(name) {
  if (S.help) { if (name === 'b' || name === 'a') toggleHelp(false); return; }
  if (name === 'lb') return setTab(S.tab - 1);
  if (name === 'rb') return setTab(S.tab + 1);
  if (name === 'start') { S.zone = ZONE.TABS; return setTab(TAB.SET); }
  const recentMax = Math.min(3, S.ranked.length);  // index recentMax is the "view more" tile
  const cards = cardCount();
  switch (name) {
    case 'up': S.zone = Math.max(ZONE.TOP, S.zone - 1); break;
    case 'down': S.zone = Math.min(S.zone + 1, cards || S.zone === ZONE.TABS ? ZONE.CARDS : ZONE.TABS); break;
    case 'left':
      if (S.zone === ZONE.TOP) S.top = 0; else if (S.zone === ZONE.RECENT) S.recent = Math.max(0, S.recent - 1);
      else if (S.zone === ZONE.TABS) S.tab = Math.max(0, S.tab - 1); else S.card = Math.max(0, S.card - 1);
      break;
    case 'right':
      if (S.zone === ZONE.TOP) S.top = 1; else if (S.zone === ZONE.RECENT) S.recent = Math.min(recentMax, S.recent + 1);
      else if (S.zone === ZONE.TABS) S.tab = Math.min(TABS.length - 1, S.tab + 1);
      else S.card = clamp(S.card + 1, 0, Math.max(0, cards - 1));
      break;
    case 'b': if (S.zone > ZONE.RECENT) S.zone = ZONE.RECENT; break;
    case 'y': return startSearch();
    case 'x':
      if (S.zone === ZONE.CARDS && S.tab === TAB.PLACES) {
        const place = S.places[S.card];
        if (place && place.kind === 'site') {
          await xbox.call('favorite_remove', { url: place.path });
          S.places = await xbox.call('places');
          S.card = clamp(S.card, 0, Math.max(0, S.places.length - 1));
          renderCards();
        }
      } else if (S.zone === ZONE.CARDS && S.tab === TAB.RUN && S.wins[S.card]) {
        markClosing(S.wins[S.card].hwnd);
        xbox.call('close', { hwnd: S.wins[S.card].hwnd });
        S.wins.splice(S.card, 1);
        S.card = clamp(S.card, 0, Math.max(0, S.wins.length - 1));
        renderCards();
      }
      break;
    case 'a': return activate();
  }
  if (S.zone === ZONE.TABS && (name === 'left' || name === 'right')) return setTab(S.tab);
  updateFocus();
}

async function activate() {
  if (S.zone === ZONE.TOP) {
    if (S.top === 0) startSearch(); else toggleHelp(true);
  } else if (S.zone === ZONE.RECENT) {
    if (S.recent < Math.min(3, S.ranked.length)) await launch(S.ranked[S.recent]);
    else openLibrary();
  } else if (S.zone === ZONE.TABS) {
    S.zone = ZONE.CARDS;
    updateFocus();
  } else if (S.tab === TAB.LIB) {
    const shown = filtered().slice(0, SHELF);
    if (S.card >= shown.length) openLibrary();
    else await launch(shown[S.card]);
  } else if (S.tab === TAB.PLACES) {
    const place = S.places[S.card];
    if (place) xbox.call('open', { path: place.path });
  } else if (S.tab === TAB.RUN) {
    const w = S.wins[S.card];
    if (w) xbox.call('focus', { hwnd: w.hwnd });
  } else {
    settingsItems()[S.card]?.run();
  }
}

function toggleHelp(show) {
  S.help = show;
  $('#help').classList.toggle('hidden', !show);
}

function startSearch() {
  if (S.view !== 'library') openLibrary();  // results are always shown in the library grid
  S.searching = true;
  $('#libSearch').focus();
  xbox.kb('show');
}

function endSearch() {
  S.searching = false;
  $('#libSearch').blur();
}

// ---- library grid -------------------------------------------------------------------------------
const LIB_COLS = 6;

function showView(view) {
  S.view = view;
  for (const id of ['home', 'library', 'switcher']) $('#' + id).classList.toggle('hidden', id !== view);
}

function openLibrary() {
  S.lib = 0;
  showView('library');
  renderLibrary();
}

function renderLibrary() {
  const apps = filtered();
  S.lib = clamp(S.lib, 0, Math.max(0, apps.length - 1));
  $('#libCount').textContent = S.filter ? `${apps.length} of ${S.apps.length}` : `${apps.length}`;
  const grid = $('#libGrid');
  grid.innerHTML = '';
  apps.forEach((app) => {
    const tile = el('div', 'tile libtile');
    tile.append(el('div', 'name', esc(app.name)));
    paint(app, tile, tile);
    grid.append(tile);
  });
  if (!apps.length) grid.append(el('div', 'empty', 'No apps match your search.'));
  focusLibrary();
}

function focusLibrary() {
  const tiles = $('#libGrid').children;
  [...tiles].forEach((t, i) => t.classList.toggle('focus', i === S.lib));
  centerIn($('#libGrid'), tiles[S.lib], 'y');
}

async function libraryButton(name) {
  const jump = { left: -1, right: 1, up: -LIB_COLS, down: LIB_COLS, lb: -LIB_COLS * 3, rb: LIB_COLS * 3 }[name];
  if (jump !== undefined) S.lib = clamp(S.lib + jump, 0, Math.max(0, filtered().length - 1));
  else if (name === 'a') {
    const app = filtered()[S.lib];
    if (app) await launch(app);
  } else if (name === 'x') {
    const app = filtered()[S.lib];
    if (app) {
      await hideApp(app);
      renderLibrary();
    }
    return;
  } else if (name === 'b') {
    showView('home');
    renderHome();
    return;
  } else if (name === 'y') return startSearch();
  focusLibrary();
}

async function hideApp(app) {
  const hidden = [...(S.cfg.hidden_apps || []), app.path];
  await xbox.call('config_set', { key: 'hidden_apps', value: hidden });
  await loadData();
}

// ---- switcher -------------------------------------------------------------------------------
async function openSwitcher(prev = 0) {
  const home = S.view !== 'switcher' ? await xbox.selfShot() : null;
  if (S.view !== 'switcher') S.returnView = S.view;
  const [wins, thumbs] = await Promise.all([xbox.call('windows'), xbox.thumbs({ w: 640, h: 360 })]);
  const byHwnd = new Map(thumbs.map((t) => [t.hwnd, t]));
  const cards = [{ xbox: true, title: 'Xbox', thumb: home }];
  for (const w of wins) {
    const t = byHwnd.get(w.hwnd);
    cards.push({ hwnd: w.hwnd, title: w.title, thumb: t?.thumb || null, icon: t?.icon || null, path: w.path, game: w.game });
  }
  const at = cards.findIndex((c) => c.hwnd && c.hwnd === prev);
  S.sw = { cards, sel: Math.max(0, at), zone: 'cards', mode: 0, prev };
  showView('switcher');
  renderSwitcher();
  xbox.focusUi();
}

function closeSwitcher() {
  showView(S.returnView || 'home');
  if (S.view === 'home') updateFocus();
}

function leaveSwitcher() {
  if (S.sw.prev) xbox.call('focus', { hwnd: S.sw.prev }); else closeSwitcher();
}

async function swIcon(card, host) {
  if (card.xbox) { host.innerHTML = XLOGO; return; }
  if (card.icon) { host.innerHTML = `<img src="${card.icon}">`; return; }
  if (card.path) {
    const url = await xbox.icon(card.path);
    if (url) host.innerHTML = `<img src="${url}">`;
  }
}

function renderSwitcher() {
  const { cards, sel } = S.sw;
  const icons = $('#swIcons');
  icons.innerHTML = '';
  icons.append(el('div', 'pillkey', 'LB'));
  const first = clamp(sel - 4, 0, Math.max(0, cards.length - 9));
  cards.slice(first, first + 9).forEach((c, i) => {
    const d = el('div', `swicon${first + i === sel ? ' sel' : ''}`);
    swIcon(c, d);
    icons.append(d);
  });
  icons.append(el('div', 'pillkey', 'RB'));

  const car = $('#swCarousel');
  if (!car.children.length || car.children.length !== cards.length) {
    car.innerHTML = '';
    cards.forEach((c) => {
      const d = el('div', 'swcard');
      const hd = el('div', 'hd');
      const ic = el('div');
      ic.style.cssText = 'width:5.3vh;height:5.3vh;flex:none;display:grid;place-items:center';
      swIcon(c, ic);
      hd.append(ic, el('span', '', esc(c.title)));
      const body = el('div', 'body');
      body.style.background = c.thumb ? `url(${c.thumb}) top center / cover` : gradient(c.xbox ? 130 : hueOf(c.title), c.xbox ? 60 : 30);
      if (c.xbox && !c.thumb) body.innerHTML = `<div class="bigx">${XLOGO}</div>`;
      const hints = el('div', 'hints', `<span><i class="g">A</i>Select</span>${c.xbox ? ''
        : '<span><i class="g">X</i>Close App</span><span><i class="g">Y</i>Controller</span>'}`);
      d.append(hd, body, hints);
      if (!c.xbox) d.append(el('div', `badge${c.game ? ' game' : ''}`, c.game ? 'Controller: game' : 'Controller: mouse'));
      car.append(d);
    });
  }
  [...car.children].forEach((d, i) => d.classList.toggle('sel', i === sel && S.sw.zone === 'cards'));
  const pitch = (47.3 + 3) * innerWidth / 100;
  car.style.transform = `translateX(${-sel * pitch}px)`;

  $('#swHints').innerHTML = '<b>A</b>Switch<b>X</b>Close<b>Y</b>Controller mode<b>Menu</b>Window options<b>LB / RB</b>Move';
  const modes = $('#swModes');
  modes.innerHTML = '';
  MODES.forEach((m, i) => {
    modes.append(el('div', `mode${i === 0 ? ' cur' : ''}${S.sw.zone === 'modes' && S.sw.mode === i ? ' focus' : ''}`,
      `${m.icon}<span>${m.label}</span>`));
  });
}

function switcherButton(name) {
  const sw = S.sw;
  const n = sw.cards.length;
  if (sw.menu) return windowMenuButton(name);
  if (name === 'guide') return leaveSwitcher();
  if (name === 'start') return openWindowMenu();
  if (sw.zone === 'modes') {
    if (name === 'left') sw.mode = Math.max(0, sw.mode - 1);
    else if (name === 'right') sw.mode = Math.min(MODES.length - 1, sw.mode + 1);
    else if (name === 'up' || name === 'b') sw.zone = 'cards';
    else if (name === 'a') { if (sw.mode === 1) return xbox.quit(); sw.zone = 'cards'; }
  } else if (name === 'left' || name === 'lb') sw.sel = Math.max(0, sw.sel - 1);
  else if (name === 'right' || name === 'rb') sw.sel = Math.min(n - 1, sw.sel + 1);
  else if (name === 'down') sw.zone = 'modes';
  else if (name === 'b') return leaveSwitcher();
  else if (name === 'a') {
    const c = sw.cards[sw.sel];
    if (c.xbox) return closeSwitcher();
    xbox.call('focus', { hwnd: c.hwnd });
  } else if (name === 'y' && sw.cards[sw.sel].hwnd) {
    // Flip this app between "it handles the controller itself" and "controller acts as a mouse".
    const card = sw.cards[sw.sel];
    xbox.call('toggle_game', { hwnd: card.hwnd }).then((game) => {
      card.game = game;
      showModeBanner(game ? 'Game mode' : 'Mouse mode', game ? 'This app keeps the controller' : 'The controller acts as a mouse', card.title);
      $('#swCarousel').innerHTML = '';
      renderSwitcher();
    });
    return;
  } else if (name === 'x' && !sw.cards[sw.sel].xbox) {
    markClosing(sw.cards[sw.sel].hwnd);
    xbox.call('close', { hwnd: sw.cards[sw.sel].hwnd });
    sw.cards.splice(sw.sel, 1);
    sw.sel = Math.min(sw.sel, sw.cards.length - 1);
    $('#swCarousel').innerHTML = '';
  }
  renderSwitcher();
}

// ---- window options (Menu in the switcher) ---------------------------------------------------
async function openWindowMenu() {
  const card = S.sw.cards[S.sw.sel];
  if (!card || card.xbox) return;
  const mons = await xbox.call('monitors');
  const items = [['Maximize', 'maximize'], ['Minimize', 'minimize'], ['Snap to the left half', 'snap_left'],
    ['Snap to the right half', 'snap_right']];
  if (mons.length > 1) items.push(['Move to the next monitor', 'next_monitor']);
  items.push(['Close', 'close']);
  S.sw.menu = { hwnd: card.hwnd, title: card.title, items, sel: 0 };
  renderWindowMenu();
}

function renderWindowMenu() {
  const host = $('#swMenu');
  const m = S.sw && S.sw.menu;
  host.classList.toggle('hidden', !m);
  if (!m) return;
  host.innerHTML = '';
  host.append(el('h3', '', esc(m.title)));
  m.items.forEach(([label], i) => host.append(el('div', `menuitem${i === m.sel ? ' focus' : ''}`, esc(label))));
}

function windowMenuButton(name) {
  const m = S.sw.menu;
  if (name === 'up') m.sel = Math.max(0, m.sel - 1);
  else if (name === 'down') m.sel = Math.min(m.items.length - 1, m.sel + 1);
  else if (name === 'b' || name === 'start' || name === 'guide') S.sw.menu = null;
  else if (name === 'a') {
    const action = m.items[m.sel][1];
    S.sw.menu = null;
    if (action === 'close') {
      markClosing(m.hwnd);
      S.sw.cards = S.sw.cards.filter((c) => c.hwnd !== m.hwnd);
      S.sw.sel = clamp(S.sw.sel, 0, S.sw.cards.length - 1);
      $('#swCarousel').innerHTML = '';
      renderSwitcher();
    }
    xbox.call('window_action', { hwnd: m.hwnd, action });
  }
  renderWindowMenu();
}

// ---- quick settings (hold the Xbox button) -----------------------------------------------------
function quickItems() {
  const on = (v) => (v ? 'On' : 'Off');
  const system = (action) => () => xbox.call('system', { action });
  const later = (action) => async () => {
    closeQuick(true);
    await new Promise((r) => setTimeout(r, 450));  // let the app we came from take the screen back first
    xbox.call('system', { action });
  };
  return [
    { title: 'Volume down', glyph: '🔉', run: system('volume_down') },
    { title: 'Volume up', glyph: '🔊', run: system('volume_up') },
    { title: 'Mute', glyph: '🔇', run: system('mute') },
    { title: 'Screenshot', glyph: '📷', run: later('screenshot') },
    { title: 'Brightness down', glyph: '🔅', state: 'built-in screens', run: system('brightness_down') },
    { title: 'Brightness up', glyph: '🔆', state: 'built-in screens', run: system('brightness_up') },
    { title: 'Wi-Fi', glyph: '📶', run: later('wifi') },
    { title: 'Bluetooth', glyph: '🎧', run: later('bluetooth') },
    { title: 'Display settings', glyph: '🖥', run: later('display') },
    { title: 'Move this UI to another display', glyph: '⇄', run: cycleDisplay },
    { title: 'Interface sounds', glyph: '🔔', state: on(S.cfg.ui_sounds !== false), run: () => toggle('ui_sounds', true) },
    { title: 'Button hints', glyph: '🎮', state: on(S.cfg.show_hints !== false), run: () => toggle('show_hints', true) },
    { title: 'Lock', glyph: '🔒', run: later('lock') },
    { title: 'Sleep', glyph: '🌙', danger: true, run: later('sleep') },
    { title: 'Restart', glyph: '↻', danger: true, run: later('restart') },
    { title: 'Shut down', glyph: '⏻', danger: true, run: later('shutdown') },
  ];
}

function openQuick(prev) {
  S.quick = { sel: 0, prev, confirm: false };
  $('#quick').classList.remove('hidden');
  renderQuick();
  xbox.focusUi();
}

function closeQuick(restore) {
  const prev = S.quick && S.quick.prev;
  S.quick = null;
  $('#quick').classList.add('hidden');
  if (restore && prev) xbox.call('focus', { hwnd: prev });
}

const BATTERY_TEXT = { empty: 'almost empty', low: 'low', medium: 'medium', full: 'full' };

function renderQuick() {
  const q = S.quick;
  if (!q) return;
  const items = quickItems();
  const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  $('#quickInfo').textContent = `${time}${S.padBattery ? `  ·  Controller battery ${BATTERY_TEXT[S.padBattery]}` : ''}`;
  const grid = $('#quickGrid');
  grid.innerHTML = '';
  items.forEach((it, i) => {
    const focus = i === q.sel;
    const state = focus && q.confirm ? 'Press A again to confirm' : it.state || '';
    grid.append(el('div', `qitem${focus ? ' focus' : ''}${it.danger ? ' danger' : ''}`,
      `<div class="glyph">${it.glyph}</div><div>${esc(it.title)}</div>${state ? `<div class="state">${esc(state)}</div>` : ''}`));
  });
  $('#quickHints').innerHTML = '<b>A</b>Select<b>B</b>Close<b>D-pad</b>Move';
}

function quickButton(name) {
  const q = S.quick;
  const items = quickItems();
  const step = { left: -1, right: 1, up: -QUICK_COLS, down: QUICK_COLS }[name];
  if (step !== undefined) {
    q.sel = clamp(q.sel + step, 0, items.length - 1);
    q.confirm = false;
  } else if (name === 'a') {
    const item = items[q.sel];
    if (item.danger && !q.confirm) q.confirm = true;  // shutting down is never one press away
    else { q.confirm = false; item.run(); }
  } else if (name === 'b' || name === 'guide' || name === 'start') {
    return closeQuick(true);
  }
  renderQuick();
}

// ---- controller battery ------------------------------------------------------------------------
const BATTERY_WIDTH = { empty: 2, low: 5, medium: 11, full: 17 };

function showPadBattery(level) {
  S.padBattery = level;
  document.querySelectorAll('.padbatt').forEach((svg) => {
    svg.classList.toggle('hidden', !level);
    svg.classList.toggle('low', level === 'low');
    svg.classList.toggle('empty', level === 'empty');
    svg.querySelector('.padfill').setAttribute('width', String(BATTERY_WIDTH[level] || 0));
  });
}

// ---- input routing ----------------------------------------------------------------------------
const CUES = { up: 'move', down: 'move', left: 'move', right: 'move', lb: 'move', rb: 'move', a: 'select', b: 'back' };

function onButton(name) {
  if (S.searching) return;  // the keyboard window owns input while searching
  window.sfx.play(CUES[name] || (name === 'guide' ? 'open' : ''));
  if (S.quick) return quickButton(name);
  if (S.view === 'switcher') switcherButton(name);
  else if (name === 'guide') openSwitcher(0);
  else if (S.view === 'library') libraryButton(name);
  else homeButton(name);
}

xbox.on('btn', onButton);
xbox.on('guide', () => {
  if (S.quick) closeQuick(true);
  else if (S.view === 'switcher') leaveSwitcher();
  else openSwitcher(0);
});
xbox.on('open-switcher', ({ prev }) => { if (S.quick) closeQuick(false); openSwitcher(prev); });
xbox.on('open-quick', ({ prev }) => { if (S.quick) closeQuick(true); else { window.sfx.play('open'); openQuick(prev); } });
xbox.on('battery', showPadBattery);
xbox.on('apps-changed', async () => {
  await loadData();
  if (S.view === 'library') renderLibrary(); else renderHome();
});
xbox.on('kb-closed', endSearch);

const KEYS = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', Enter: 'a', Escape: 'b',
  x: 'x', y: 'y', q: 'lb', e: 'rb', s: 'start', F1: 'guide' };
addEventListener('keydown', (ev) => {
  if (document.activeElement === $('#libSearch')) {
    if (ev.key === 'Enter' || ev.key === 'Escape') { xbox.kb('hide'); endSearch(); }
    return;
  }
  if (S.view === 'library' && ev.key.length === 1 && !ev.ctrlKey && !ev.altKey && !ev.metaKey) {
    S.searching = true;  // a physical keyboard types straight into the search box
    $('#libSearch').focus();
    return;
  }
  if (KEYS[ev.key]) { ev.preventDefault(); onButton(KEYS[ev.key]); }
});

function onFilterInput(ev) {
  S.filter = ev.target.value;
  if (S.view === 'library') {
    S.lib = 0;
    renderLibrary();
    return;
  }
  S.tab = 0;
  S.card = 0;
  renderCards();
  updateFocus();
}
$('#libSearch').addEventListener('input', onFilterInput);

// ---- boot ---------------------------------------------------------------------------------------
// ---- live window list -------------------------------------------------------------------------
// While the switcher or the Running tab is on screen, notice windows opening and closing (also ones closed from
// elsewhere), and refresh thumbnails every few seconds.
let windowSignature = '';
let thumbsAt = 0;
let polling = false;

function applyWindows(wins, thumbs) {
  const merged = mergeWindows(wins, thumbs).filter((w) => !(closing.get(w.hwnd) > Date.now()));
  if (S.view === 'switcher') {
    const sw = S.sw;
    const keep = sw.cards[sw.sel]?.hwnd;
    sw.cards = [sw.cards[0], ...merged.map((w) => ({ hwnd: w.hwnd, title: w.title, thumb: w.thumb, icon: w.icon, path: w.path, game: w.game }))];
    const at = keep ? sw.cards.findIndex((c) => c.hwnd === keep) : -1;
    sw.sel = at >= 0 ? at : clamp(sw.sel, 0, sw.cards.length - 1);
    $('#swCarousel').innerHTML = '';
    renderSwitcher();
  } else {
    S.wins = merged;
    S.card = clamp(S.card, 0, Math.max(0, S.wins.length - 1));
    renderCards();
    updateFocus();
  }
}

async function pollWindows() {
  const watching = S.view === 'switcher' || (S.view === 'home' && S.tab === TAB.RUN);
  if (!watching || polling || !S.sw && S.view === 'switcher') return;
  polling = true;
  try {
    const wins = await xbox.call('windows');
    const signature = wins.map((w) => `${w.hwnd}:${w.title}`).join('|');
    if (signature === windowSignature && Date.now() - thumbsAt < 5000) return;
    windowSignature = signature;
    thumbsAt = Date.now();
    applyWindows(wins, await xbox.thumbs({ w: 640, h: 360 }));
  } finally {
    polling = false;
  }
}

function tickClock() {
  const t = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  $('#clock').textContent = t;
  $('#swClock').textContent = t;
}

if (navigator.getBattery) {
  navigator.getBattery().then((b) => {
    const show = () => { $('#swBattFill').setAttribute('width', String(Math.max(1, Math.round(17 * b.level)))); };
    show();
    b.addEventListener('levelchange', show);
  }).catch(() => {});
}

(async () => {
  xbox.padState().then((state) => showPadBattery(state.battery));
  tickClock();
  setInterval(tickClock, 10000);
  setInterval(pollWindows, 1000);
  await loadData();
  renderHome();
  const view = new URLSearchParams(location.search).get('view');
  if (view === 'switcher') openSwitcher(0);
  else if (view === 'places') { S.zone = ZONE.CARDS; await setTab(TAB.PLACES); }
  else if (view === 'running') { S.zone = ZONE.CARDS; await setTab(TAB.RUN); }
  else if (view === 'settings') { S.zone = ZONE.CARDS; await setTab(TAB.SET); }
  else if (view === 'quick') openQuick(0);
  else if (view === 'menu') { await openSwitcher(0); S.sw.sel = Math.min(1, S.sw.cards.length - 1); openWindowMenu(); }
  else if (view === 'help') toggleHelp(true);
  else if (view === 'library') openLibrary();
})();
})();

// A big, brief notice so a controller-mode flip in the switcher is impossible to miss.
let modeBannerTimer = 0;
function showModeBanner(title, sub, app) {
  document.getElementById('modeBanner')?.remove();
  const b = el('div', 'modeBanner');
  b.id = 'modeBanner';
  b.append(el('div', 'mbTitle', title), el('div', 'mbSub', sub), el('div', 'mbApp', app || ''));
  document.body.appendChild(b);
  clearTimeout(modeBannerTimer);
  modeBannerTimer = setTimeout(() => b.remove(), 1800);
}
