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
