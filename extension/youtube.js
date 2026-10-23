'use strict';
console.info('[xbox-yt] content script loaded on', location.pathname);
// Regular YouTube, driven by a controller. While Xbox Mode is running the page keeps its own look; this adds D-pad
// navigation between the page's controls, A to activate, B to go back, Y to search, LB/RB to scroll (volume on a
// video) and Menu to move between the player and the rest of the page.
// The D-pad and B arrive as arrow keys and Esc; A, Y, LB, RB and Menu are read from the Gamepad API.
const POLL_MS = 2000;
const HINTS_MS = 6000;
const NAV_SELECTOR = 'a[href], button, input, select, textarea, summary, [role="button"], [role="tab"], [role="link"], [tabindex]:not([tabindex="-1"])';
const TEXT_INPUT = 'input:not([type=button]):not([type=checkbox]):not([type=radio]):not([type=submit]):not([type=range]), textarea, [contenteditable=""], [contenteditable="true"]';
const SEARCH_BOX = 'input#search, input[name="search_query"]';
const TILE = 'ytd-rich-item-renderer, ytd-video-renderer, ytd-compact-video-renderer, ytd-grid-video-renderer, ytd-playlist-video-renderer, ytd-playlist-renderer, ytd-channel-renderer, ytd-reel-item-renderer, yt-lockup-view-model';
const root = document.documentElement;

let active = false;
let keyboardOpen = false;
let padNav = false;     // the controller, not the mouse cursor, is choosing what to act on
let marked = null;
let polled = false;
let lastReason;
let hintsEl = null;

// ---- link to Xbox Mode ----------------------------------------------------------
function poll() {
  if (document.hidden && polled) return;  // a background tab still checks once, so it is ready when you switch to it
  polled = true;
  try {
    chrome.runtime.sendMessage({ type: 'status' }, (s) => {
      const err = chrome.runtime.lastError;
      setActive(!err && Boolean(s && s.running), err ? err.message : s && s.error);
    });
  } catch (e) { setActive(false, `extension was reloaded, refresh this tab (${e.message})`); }
}

function setActive(on, why) {
  const reason = on ? 'Xbox Mode is running' : `Xbox Mode not detected${why ? `: ${why}` : ''}`;
  if (reason !== lastReason) { console.info(`[xbox-yt] controller support ${on ? 'on' : 'off'} - ${reason}`); lastReason = reason; }
  if (on === active) return;
  active = on;
  root.classList.toggle('xbox-yt-active', on);
  if (on) showHints(); else { mark(null); hideHints(); setKeyboard(false); padNav = false; }
}

function setKeyboard(show) {
  if (show === keyboardOpen) return;
  keyboardOpen = show;
  try { chrome.runtime.sendMessage({ type: 'keyboard', action: show ? 'show' : 'hide' }); } catch { /* extension reloaded */ }
}

// ---- small on-screen hints ------------------------------------------------------------
function showHints() {
  hideHints();
  hintsEl = document.createElement('div');
  hintsEl.id = 'xb-hints';
  hintsEl.textContent = 'D-pad Move   A Select   B Back   Y Search   LB/RB Scroll   Menu Player / page';
  document.body.appendChild(hintsEl);
  setTimeout(hideHints, HINTS_MS);
}

function hideHints() {
  if (hintsEl) { hintsEl.remove(); hintsEl = null; }
}

// ---- navigation ------------------------------------------------------------------------
const onWatch = () => location.pathname === '/watch';
const inPlayer = (n) => Boolean(n && n.closest && n.closest('#movie_player'));
const isTextField = (n) => Boolean(n && n.matches && n.matches(`${TEXT_INPUT}, select, [role="slider"]`));

function mark(el) {
  if (marked) marked.removeAttribute('data-xb-focus');
  marked = el;
  if (el) el.setAttribute('data-xb-focus', '');
}

function visible(el) {
  const r = el.getBoundingClientRect();
  if (r.width < 4 || r.height < 4 || el.disabled) return false;
  const s = getComputedStyle(el);
  return s.visibility !== 'hidden' && s.display !== 'none' && r.bottom > -window.innerHeight * 0.5 && r.top < window.innerHeight * 1.5;
}

function candidates() {
  const seen = new Set();
  const out = [];
  const tiles = new Set();
  for (const el of document.querySelectorAll(NAV_SELECTOR)) {
    if (!visible(el) || el.closest('#xb-hints')) continue;
    // A video tile is one stop: its first link. The channel name, the three-dot menu and the other buttons inside it
    // are skipped, so the D-pad moves from video to video.
    const tile = el.closest(TILE);
    if (tile) {
      if (tiles.has(tile) || el.tagName !== 'A') continue;
      tiles.add(tile);
    }
    // A video tile has several links to the same page (thumbnail, title); keep only the first.
    const href = el.tagName === 'A' ? el.href : '';
    if (href && /\/(watch|shorts|playlist)|\/@|\/channel\//.test(href)) {
      if (seen.has(href)) continue;
      seen.add(href);
    }
    out.push(el);
  }
  return out;
}

const center = (r) => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 });

function pick(from, dir) {
  const a = center(from.getBoundingClientRect());
  let best = null;
  let bestScore = Infinity;
  for (const el of candidates()) {
    if (el === from || from.contains(el) || el.contains(from)) continue;
    const b = center(el.getBoundingClientRect());
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const along = dir === 'ArrowUp' ? -dy : dir === 'ArrowDown' ? dy : dir === 'ArrowLeft' ? -dx : dx;
    if (along <= 1) continue;
    const score = along + Math.abs(dir === 'ArrowUp' || dir === 'ArrowDown' ? dx : dy) * 2.5;
    if (score < bestScore) { best = el; bestScore = score; }
  }
  return best;
}

// Where the controller starts: the first video on screen, otherwise the first control on screen.
function firstOnScreen() {
  const onScreen = candidates().filter((el) => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight; });
  return onScreen.find((el) => el.tagName === 'A' && /\/watch\?/.test(el.href)) || onScreen[0] || null;
}

function goTo(el) {
  if (!el) return;
  padNav = true;
  navMouse = lastMouse;
  el.focus({ preventScroll: true });
  mark(el);
  // Scroll at once: a smooth scroll leaves the next D-pad press measuring tiles that are still moving, which skips videos.
  const r = el.getBoundingClientRect();
  if (r.top < window.innerHeight * 0.15 || r.bottom > window.innerHeight * 0.85) el.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
}

function goBack() {
  const cur = document.activeElement;
  if (isTextField(cur)) { cur.blur(); return true; }
  if (location.pathname !== '/' && history.length > 1) { history.back(); return true; }
  return false;
}

window.addEventListener('keydown', (e) => {
  if (!active) return;
  if (e.key === 'Escape') {
    if (document.fullscreenElement) return;  // B leaves full screen the normal way
    if (goBack()) { e.preventDefault(); e.stopImmediatePropagation(); }
    return;
  }
  if (!e.key.startsWith('Arrow') || e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
  const cur = document.activeElement;
  if (isTextField(cur)) return;
  // In the player the arrows already seek and change the volume.
  if (onWatch() && (inPlayer(cur) || !cur || cur === document.body)) return;
  e.preventDefault();
  e.stopImmediatePropagation();
  // Continue from what the controller last picked; otherwise (YouTube may have focused some button itself) start at the
  // first video on screen.
  goTo(padNav && marked && cur === marked ? pick(cur, e.key) || cur : firstOnScreen());
}, true);

// The mouse takes over again only when the cursor has really travelled away from where it sat when the D-pad last picked
// something. A little stick drift, or the movement-less mousemove Chrome fires when the page scrolls under a still
// cursor, must not hand control back.
const TAKEOVER_PX = 40;
let lastMouse = null;  // [screenX, screenY] of the latest mouse event
let navMouse = null;   // where the cursor was when the D-pad last picked something
const farFrom = (ref, e) => Boolean(ref) && Math.hypot(e.screenX - ref[0], e.screenY - ref[1]) > TAKEOVER_PX;

document.addEventListener('mousemove', (e) => {
  lastMouse = [e.screenX, e.screenY];
  if (padNav && farFrom(navMouse, e)) { padNav = false; mark(null); }
}, true);

// Xbox Mode's A is a left click at the mouse cursor. While the controller is choosing, that click is really "select what
// the D-pad picked": swallow it and activate the chosen item instead.
function fromController(e) {
  return active && padNav && e.isTrusted && e.button === 0 && !farFrom(navMouse, e);
}
// Cancelling pointerdown stops Chrome from sending the mousedown that follows, so the activation happens on whichever of
// the two arrives first.
let lastActivation = 0;
for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click', 'dblclick']) {
  document.addEventListener(type, (e) => {
    if (!fromController(e)) return;
    e.preventDefault();
    e.stopImmediatePropagation();
    if ((type === 'pointerdown' || type === 'mousedown') && performance.now() - lastActivation > 300) {
      lastActivation = performance.now();
      activate();
    }
  }, true);
}

document.addEventListener('focusin', (e) => { if (active) setKeyboard(isTextField(e.target) && !e.target.matches('select, [role="slider"]')); }, true);
document.addEventListener('focusout', (e) => { if (active && isTextField(e.target)) setKeyboard(false); }, true);

// ---- gamepad buttons the keyboard cannot express --------------------------------------
function video() { return document.querySelector('#movie_player video'); }

function activate() {
  const cur = document.activeElement;
  if (onWatch() && (inPlayer(cur) || !cur || cur === document.body)) {
    const v = video();
    if (v) { if (v.paused) v.play(); else v.pause(); }
  } else {
    const target = marked && marked.isConnected ? marked : cur;
    if (!target || target === document.body) return;
    // YouTube's own handlers ignore a script-made click on a link, so follow links directly.
    if (target.tagName === 'A' && target.href && target.target !== '_blank') location.assign(target.href);
    else target.click();
  }
}

function toggleZone() {
  const cur = document.activeElement;
  if (inPlayer(cur) || !cur || cur === document.body) {
    goTo(candidates().find((el) => el.tagName === 'A' && /\/watch\?/.test(el.href) && !inPlayer(el)));
  } else {
    const player = document.querySelector('#movie_player');
    if (player) { player.focus(); mark(null); }
  }
}

const down = {};
function pads() {
  const pad = Array.from(navigator.getGamepads()).find(Boolean);
  if (pad && active) {
    const press = (i) => { const now = pad.buttons[i] && pad.buttons[i].pressed; const was = down[i]; down[i] = now; return now && !was; };
    const y = press(3);
    const lb = press(4);
    const rb = press(5);
    const menu = press(9);
    if (y) { const box = document.querySelector(SEARCH_BOX); if (box) { goTo(box); box.select(); } }
    if (menu && onWatch()) toggleZone();
    if (lb || rb) {
      const v = onWatch() && video();
      if (v) v.volume = Math.min(1, Math.max(0, v.volume + (rb ? 0.1 : -0.1)));
      else window.scrollBy({ top: (rb ? 1 : -1) * window.innerHeight * 0.8, behavior: 'smooth' });
    }
  }
  requestAnimationFrame(pads);
}

poll();
setInterval(poll, POLL_MS);
requestAnimationFrame(pads);
