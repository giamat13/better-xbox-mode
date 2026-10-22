// Relays the content script's state to the desktop app on localhost. Silent when the app is not running.
const ENDPOINT = 'http://127.0.0.1:8765/heartbeat';

chrome.runtime.onMessage.addListener((message) => {
  if (!message || message.type !== 'heartbeat') return false;
  fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ state: message.state }),
  }).catch(() => {});
  return false;
});
