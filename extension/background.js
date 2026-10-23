'use strict';
// Talks to the Xbox Mode bridge on behalf of the content scripts.
const BASE = 'http://127.0.0.1:47821';
const HEADERS = { 'X-Xbox-Mode-Extension': '1' };
let lastError = null;

async function status() {
  try {
    const res = await fetch(`${BASE}/status`, { headers: HEADERS, signal: AbortSignal.timeout(1500) });
    if (!res.ok) throw new Error(`bridge answered HTTP ${res.status}`);
    const s = await res.json();
    if (lastError) { console.info('[xbox-yt] bridge reachable again'); lastError = null; }
    return s;
  } catch (e) {
    if (String(e) !== lastError) { console.warn('[xbox-yt] bridge not reachable:', String(e)); lastError = String(e); }
    return { running: false, pad: false, error: String(e) };
  }
}

// ---- game sites ------------------------------------------------------------
// Sites the user marked as "game": while such a tab is in front, Xbox Mode leaves the mouse alone so the page's own
// controller support works. Clicking the toolbar icon marks or unmarks the current site.
function siteOf(url) {
  try {
    const u = new URL(url);
    return /^https?:$/.test(u.protocol) ? u.hostname.replace(/^www\./, '') : '';
  } catch {
    return '';
  }
}

async function gameSites() {
  const { gameSites: list } = await chrome.storage.local.get('gameSites');
  return Array.isArray(list) ? list : [];
}

async function activeTab() {
  const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tab;
}

async function syncGameTab() {
  const tab = await activeTab();
  const site = tab ? siteOf(tab.url || '') : '';
  const game = Boolean(site) && (await gameSites()).includes(site);
  if (tab) chrome.action.setBadgeText({ tabId: tab.id, text: game ? 'ON' : '' });
  fetch(`${BASE}/tab`, {
    method: 'POST', headers: { ...HEADERS, 'Content-Type': 'application/json' }, body: JSON.stringify({ game }),
  }).catch(() => {});
}

async function toggleGameSite(tab) {
  const site = siteOf(tab && tab.url || '');
  if (!site) return;
  const list = await gameSites();
  await chrome.storage.local.set({ gameSites: list.includes(site) ? list.filter((s) => s !== site) : [...list, site] });
}

chrome.action.onClicked.addListener(toggleGameSite);
chrome.commands.onCommand.addListener(async (name) => {
  if (name === 'toggle-game-site') toggleGameSite(await activeTab());
});

chrome.tabs.onActivated.addListener(syncGameTab);
chrome.tabs.onUpdated.addListener((_id, change) => { if (change.url || change.status === 'complete') syncGameTab(); });
chrome.windows.onFocusChanged.addListener(syncGameTab);
chrome.storage.onChanged.addListener(syncGameTab);
chrome.runtime.onStartup.addListener(syncGameTab);
chrome.runtime.onInstalled.addListener(() => {
  chrome.action.setBadgeBackgroundColor({ color: '#107c10' });
  syncGameTab();
});

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg.type === 'status') {
    status().then(reply);
    return true;
  }
  if (msg.type === 'keyboard') {
    fetch(`${BASE}/keyboard`, {
      method: 'POST', headers: { ...HEADERS, 'Content-Type': 'application/json' }, body: JSON.stringify({ action: msg.action }),
    }).catch(() => {});
  }
  return false;
});
