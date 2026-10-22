// End-to-end tests for the Chrome extension. Runs headless Chromium with the unpacked extension,
// a fake gamepad injected into the page, and (for the heartbeat test) the real desktop heartbeat server.
//
// Run from the repository root:
//   npm install --no-save playwright@1.56.1 && npx playwright install chromium
//   node --test tests/e2e/extension.test.cjs
const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const EXTENSION_DIR = path.join(ROOT, 'extension');
const CHROME = process.env.CHROME_PATH || chromium.executablePath();
const PYTHON = process.env.PYTHON || 'python3';
const HEARTBEAT_PORT = 8765;

const BUTTON = { A: 0, Y: 3, LB: 4, RB: 5 };
const FAKE_PAD_SCRIPT = `(() => {
  const realGetGamepads = Navigator.prototype.getGamepads;
  const pad = {
    id: 'Fake Xbox Controller', index: 0, connected: true, mapping: 'standard', timestamp: 0,
    axes: [0, 0, 0, 0],
    buttons: Array.from({ length: 17 }, () => ({ pressed: false, touched: false, value: 0 })),
  };
  window.__pad = pad;
  window.__padOn = false;
  Navigator.prototype.getGamepads = function () {
    return window.__padOn ? [pad] : realGetGamepads.call(this);
  };
})();`;

const PAGES = {
  '/dashboard.html': `<!doctype html><html><body style="margin:0">
    <nav id="session-list">
      <div class="session-item" data-id="a" aria-current="true">first</div>
      <div class="session-item" data-id="b" aria-current="false">second</div>
      <div class="session-item" data-id="c" aria-current="false">third</div>
    </nav>
    <script>
      window.selected = [];
      for (const item of document.querySelectorAll('.session-item')) {
        item.addEventListener('click', () => {
          window.selected.push(item.dataset.id);
          for (const other of document.querySelectorAll('.session-item'))
            other.setAttribute('aria-current', String(other === item));
        });
      }
    </script></body></html>`,
  '/click.html': `<!doctype html><html><body style="margin:0">
    <button id="target" style="position:absolute;left:100px;top:100px;width:200px;height:80px">target</button>
    <script>
      window.clicks = 0; window.events = [];
      const target = document.getElementById('target');
      target.addEventListener('click', () => window.clicks++);
      for (const type of ['mouseover', 'mousedown', 'mouseup', 'click'])
        target.addEventListener(type, () => window.events.push(type));
    </script></body></html>`,
  '/scroll.html': `<!doctype html><html><body style="margin:0">
    <div id="box" style="position:absolute;left:400px;top:200px;width:480px;height:320px;overflow:auto">
      <div style="height:3000px">long content</div></div></body></html>`,
  '/drag.html': `<!doctype html><html><body style="margin:0">
    <div id="pad" style="position:absolute;left:490px;top:260px;width:300px;height:200px;background:#999"></div>
    <script>
      window.events = [];
      const pad = document.getElementById('pad');
      for (const type of ['mousedown', 'mouseup', 'mousemove', 'click'])
        document.addEventListener(type, (e) => window.events.push({ type, buttons: e.buttons }));
    </script></body></html>`,
  '/type.html': `<!doctype html><html><body style="margin:0">
    <input id="field" style="position:absolute;left:100px;top:100px;width:300px;height:40px">
    <script>
      window.inputEvents = 0;
      document.getElementById('field').addEventListener('input', () => window.inputEvents++);
    </script></body></html>`,
  '/aware.html': `<!doctype html><html><body style="margin:0">
    <button id="target" style="position:absolute;left:100px;top:100px;width:200px;height:80px">target</button>
    <script>
      window.clicks = 0;
      window.addEventListener('gamepadconnected', () => {});
      document.getElementById('target').addEventListener('click', () => window.clicks++);
    </script></body></html>`,
  '/aware-poll.html': `<!doctype html><html><body style="margin:0">
    <script>
      window.padsSeen = 0;
      const poll = () => {
        const pads = navigator.getGamepads();
        for (const pad of pads) if (pad) window.padsSeen++;
        requestAnimationFrame(poll);
      };
      requestAnimationFrame(poll);
    </script></body></html>`,
};

let server;
let baseUrl;
let context;
let profileDir;

function startFixtureServer() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const html = PAGES[req.url.split('?')[0]];
      if (!html) {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(html);
    });
    srv.listen(0, '127.0.0.1', () => resolve(srv));
  });
}

async function frames(page, count = 3) {
  await page.evaluate(
    (n) =>
      new Promise((resolve) => {
        let left = n;
        const step = () => (--left <= 0 ? resolve() : requestAnimationFrame(step));
        requestAnimationFrame(step);
      }),
    count,
  );
}

async function enablePad(page) {
  await page.evaluate(() => {
    window.__padOn = true;
  });
  await frames(page, 2);
}

async function setAxes(page, axes) {
  await page.evaluate((values) => {
    window.__pad.axes = values;
  }, axes);
}

async function setButton(page, index, pressed) {
  await page.evaluate(
    ([i, down]) => {
      window.__pad.buttons[i].pressed = down;
    },
    [index, pressed],
  );
  await frames(page, 4);
}

async function tap(page, index) {
  await setButton(page, index, true);
  await setButton(page, index, false);
}

async function cursorPosition(page) {
  return page.evaluate(() => {
    const el = document.getElementById('xbox-mode-cursor');
    if (!el || el.style.display === 'none') return null;
    const match = /translate\((-?[\d.]+)px, (-?[\d.]+)px\)/.exec(el.style.transform);
    return match ? { x: Number(match[1]) + 14, y: Number(match[2]) + 14 } : null;
  });
}

async function moveCursorTo(page, x, y) {
  for (let step = 0; step < 600; step++) {
    const at = await cursorPosition(page);
    assert.ok(at, 'cursor overlay must be visible before moving it');
    const dx = x - at.x;
    const dy = y - at.y;
    const distance = Math.hypot(dx, dy);
    if (distance < 5) {
      await setAxes(page, [0, 0, 0, 0]);
      return at;
    }
    const magnitude = distance > 120 ? 0.9 : 0.5;
    await setAxes(page, [(dx / distance) * magnitude, (dy / distance) * magnitude, 0, 0]);
    await frames(page, 2);
  }
  throw new Error(`cursor did not reach (${x}, ${y})`);
}

async function centerOf(page, selector) {
  return page.evaluate((sel) => {
    const rect = document.querySelector(sel).getBoundingClientRect();
    return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
  }, selector);
}

async function openPage(name, { activate = false } = {}) {
  const page = await context.newPage();
  await page.goto(baseUrl + name);
  await page.waitForFunction(() => typeof window.__pad === 'object');
  await enablePad(page);
  if (activate) {
    await tap(page, BUTTON.A);
    await frames(page, 3);
  }
  return page;
}

async function heartbeatStatus() {
  const response = await fetch(`http://127.0.0.1:${HEARTBEAT_PORT}/status`);
  return response.json();
}

before(async () => {
  server = await startFixtureServer();
  baseUrl = `http://127.0.0.1:${server.address().port}`;
  profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xbox-mode-profile-'));
  context = await chromium.launchPersistentContext(profileDir, {
    executablePath: CHROME,
    headless: true,
    viewport: { width: 1280, height: 720 },
    args: [`--disable-extensions-except=${EXTENSION_DIR}`, `--load-extension=${EXTENSION_DIR}`],
  });
  await context.addInitScript(FAKE_PAD_SCRIPT);
});

after(async () => {
  if (context) await context.close();
  if (server) server.close();
  if (profileDir) fs.rmSync(profileDir, { recursive: true, force: true });
});

test('stays idle until a controller button is pressed, then shows the cursor', async () => {
  const page = await openPage('/click.html');
  assert.equal(await cursorPosition(page), null);
  await tap(page, BUTTON.A);
  await frames(page, 3);
  assert.ok(await cursorPosition(page), 'cursor should appear after the first press');
  await page.close();
});

test('left stick moves the cursor and A clicks the element under it', async () => {
  const page = await openPage('/click.html', { activate: true });
  const target = { x: 200, y: 140 };
  await moveCursorTo(page, target.x, target.y);
  assert.equal(await page.evaluate(() => window.clicks), 0, 'activation press must not click');
  await tap(page, BUTTON.A);
  await frames(page, 3);
  assert.equal(await page.evaluate(() => window.clicks), 1);
  const events = await page.evaluate(() => window.events);
  assert.ok(events.includes('mouseover'), `events: ${events}`);
  assert.ok(events.includes('mousedown'), `events: ${events}`);
  assert.ok(events.includes('click'), `events: ${events}`);
  await page.close();
});

test('right stick scrolls the scrollable element under the cursor', async () => {
  const page = await openPage('/scroll.html', { activate: true });
  await setAxes(page, [0, 0, 0, 0.8]);
  await page.waitForTimeout(500);
  await setAxes(page, [0, 0, 0, 0]);
  const scrolled = await page.evaluate(() => document.getElementById('box').scrollTop);
  assert.ok(scrolled > 100, `scrollTop was ${scrolled}`);
  await page.close();
});

test('holding A while moving the stick drags without a click', async () => {
  const page = await openPage('/drag.html', { activate: true });
  await setButton(page, BUTTON.A, true);
  await setAxes(page, [0.9, 0, 0, 0]);
  await page.waitForTimeout(300);
  await setAxes(page, [0, 0, 0, 0]);
  await setButton(page, BUTTON.A, false);
  const events = await page.evaluate(() => window.events);
  const types = events.map((e) => e.type);
  assert.ok(types.includes('mousedown'), `events: ${JSON.stringify(events)}`);
  assert.ok(events.some((e) => e.type === 'mousemove' && e.buttons === 1), 'drag should send mousemove with button held');
  assert.ok(types.includes('mouseup'), `events: ${JSON.stringify(events)}`);
  assert.ok(!types.includes('click'), 'a drag must not produce a click');
  await page.close();
});

test('Y opens the on-screen keyboard and keys type into the focused field', async () => {
  const page = await openPage('/type.html', { activate: true });
  await page.focus('#field');
  await frames(page, 2);
  await tap(page, BUTTON.Y);
  await frames(page, 3);
  for (const letter of ['h', 'i']) {
    await moveCursorTo(page, ...Object.values(await centerOf(page, `[data-xbox-osk-key="${letter}"]`)));
    await tap(page, BUTTON.A);
    await frames(page, 3);
  }
  assert.equal(await page.inputValue('#field'), 'hi');
  assert.equal(await page.evaluate(() => window.inputEvents), 2);
  await tap(page, BUTTON.Y);
  await frames(page, 3);
  const oskVisible = await page.evaluate(() => {
    const osk = document.getElementById('xbox-mode-osk');
    return !!osk && osk.style.display !== 'none';
  });
  assert.equal(oskVisible, false, 'second Y press should close the keyboard');
  await page.close();
});

test('pushing the stick past the top edge hands the mouse to the desktop app', async () => {
  const page = await openPage('/click.html', { activate: true });
  await setAxes(page, [0, -1, 0, 0]);
  await page.waitForTimeout(1500);
  await setAxes(page, [0, 0, 0, 0]);
  assert.equal(await cursorPosition(page), null, 'cursor should hide once it is pushed off the page');
  await tap(page, BUTTON.A);
  await frames(page, 3);
  assert.ok(await cursorPosition(page), 'a button press should bring the page cursor back');
  await page.close();
});

test('LB and RB move between sessions on the session dashboard without the cursor', async () => {
  const page = await openPage('/dashboard.html');
  await tap(page, BUTTON.RB);
  await frames(page, 2);
  await tap(page, BUTTON.RB);
  await frames(page, 2);
  assert.deepEqual(await page.evaluate(() => window.selected), ['b', 'c']);
  await tap(page, BUTTON.LB);
  await frames(page, 2);
  assert.deepEqual(await page.evaluate(() => window.selected), ['b', 'c', 'b']);
  assert.equal(await cursorPosition(page), null, 'session switching must not show the cursor');
  await page.close();
});

test('LB activates the cursor on a page without a session list', async () => {
  const page = await openPage('/click.html');
  await tap(page, BUTTON.LB);
  await frames(page, 3);
  assert.ok(await cursorPosition(page), 'LB should act as the first press on ordinary pages');
  await page.close();
});

test('a page that reads gamepads itself keeps the extension passive', async () => {
  const page = await openPage('/aware.html');
  await frames(page, 5);
  await tap(page, BUTTON.A);
  await setAxes(page, [1, 0, 0, 0]);
  await page.waitForTimeout(300);
  await setAxes(page, [0, 0, 0, 0]);
  assert.equal(await cursorPosition(page), null, 'no cursor on a gamepad-aware page');
  assert.equal(await page.evaluate(() => window.clicks), 0);
  await page.close();
});

test('a page that only polls getGamepads in its own loop is also passive', async () => {
  const page = await openPage('/aware-poll.html');
  await page.waitForTimeout(300);
  assert.ok((await page.evaluate(() => window.padsSeen)) > 0, 'page should still see the pad');
  await tap(page, BUTTON.A);
  await frames(page, 3);
  assert.equal(await cursorPosition(page), null);
  await page.close();
});

test('heartbeat reaches the desktop app and reports handling or native', async () => {
  const app = spawn(
    PYTHON,
    [
      '-c',
      `import time; from xbox_mode.heartbeat import HeartbeatStore, HeartbeatServer;` +
        `s = HeartbeatServer(${HEARTBEAT_PORT}, HeartbeatStore()); s.start(); time.sleep(120)`,
    ],
    { cwd: ROOT, stdio: 'ignore' },
  );
  try {
    const plain = await openPage('/click.html');
    let status;
    for (let i = 0; i < 40; i++) {
      await plain.waitForTimeout(150);
      status = await heartbeatStatus().catch(() => null);
      if (status && status.state === 'handling') break;
    }
    assert.equal(status && status.state, 'handling', JSON.stringify(status));

    const aware = await openPage('/aware.html');
    await aware.bringToFront();
    for (let i = 0; i < 40; i++) {
      await aware.waitForTimeout(150);
      status = await heartbeatStatus().catch(() => null);
      if (status && status.state === 'native') break;
    }
    assert.equal(status && status.state, 'native', JSON.stringify(status));
    await plain.close();
    await aware.close();
  } finally {
    app.kill();
  }
});
