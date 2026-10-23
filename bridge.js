'use strict';
// Local HTTP bridge so the browser extension can tell that Xbox Mode is running and can ask for the on-screen keyboard.
// Only requests that come from a browser extension are answered: a web page always sends an http(s) Origin, which is
// refused, so no site can probe or drive this.
const http = require('http');

const PORT = 47821;
const HOST = '127.0.0.1';

function startBridge({ getState, onKeyboard, onTab = () => {}, onQuit = () => {} }) {
  const server = http.createServer((req, res) => {
    const origin = req.headers.origin || '';
    // A page cannot add a custom header without a preflight, which is refused below, so the header proves an extension
    // (some browsers leave the Origin off extension requests).
    const extension = /^(chrome|moz)-extension:\/\//.test(origin) || (!/^https?:/.test(origin) && req.headers['x-xbox-mode-extension'] === '1');
    const hostOk = req.headers.host === `${HOST}:${PORT}` || req.headers.host === `localhost:${PORT}`;
    if (!extension || !hostOk) {
      res.writeHead(403).end();
      return;
    }
    const cors = { 'Access-Control-Allow-Origin': origin || '*', 'Access-Control-Allow-Methods': 'GET, POST', 'Access-Control-Allow-Headers': 'Content-Type, X-Xbox-Mode-Extension', Vary: 'Origin' };
    if (req.method === 'OPTIONS') {
      res.writeHead(204, cors).end();
      return;
    }
    if (req.method === 'GET' && req.url === '/status') {
      res.writeHead(200, { ...cors, 'Content-Type': 'application/json' }).end(JSON.stringify(getState()));
      return;
    }
    if (req.method === 'POST' && req.url === '/keyboard') {
      let body = '';
      req.on('data', (c) => { if (body.length < 1024) body += c; });
      req.on('end', () => {
        let action = '';
        try { action = JSON.parse(body).action; } catch { /* ignore */ }
        if (action === 'show' || action === 'hide') onKeyboard(action);
        res.writeHead(204, cors).end();
      });
      return;
    }
    if (req.method === 'POST' && req.url === '/quit') {
      res.writeHead(204, cors).end();
      onQuit();
      return;
    }
    if (req.method === 'POST' && req.url === '/tab') {
      let body = '';
      req.on('data', (c) => { if (body.length < 1024) body += c; });
      req.on('end', () => {
        let game = false;
        try { game = JSON.parse(body).game === true; } catch { /* ignore */ }
        onTab(game);
        res.writeHead(204, cors).end();
      });
      return;
    }
    res.writeHead(404, cors).end();
  });
  server.on('error', (e) => console.error('Extension bridge unavailable:', e.message));
  server.listen(PORT, HOST);
  return server;
}

module.exports = { startBridge, PORT };
