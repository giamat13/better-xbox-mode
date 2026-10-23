'use strict';
const { app, BrowserWindow, ipcMain, Notification, screen, desktopCapturer, nativeImage, shell } = require('electron');
const { spawn } = require('child_process');
const readline = require('readline');
const fs = require('fs');
const path = require('path');
const { canShowWindow } = require('./pe');
const { startBridge } = require('./bridge');

const args = process.argv.slice(2);
const argValue = (name) => (args.find((a) => a.startsWith(`--${name}=`)) || '').split('=').slice(1).join('=');
const SHOT = argValue('screenshot');
const VIEW = argValue('view');
const WINDOWED = args.includes('--windowed') || Boolean(SHOT);

let win = null;
let kbWin = null;
let engine = null;
let nextId = 1;
let uiHwnd = 0;
let padConnected = false;
let padBattery = null;
let displayId = null;  // the display the UI lives on; null means the main one
const pending = new Map();

// ---- Python engine bridge -------------------------------------------------
function post(msg) {
  if (engine && engine.stdin.writable) engine.stdin.write(JSON.stringify(msg) + '\n');
}

function call(cmd, extra = {}) {
  return new Promise((resolve) => {
    const id = nextId++;
    pending.set(id, resolve);
    post({ id, cmd, ...extra });
  });
}

function startEngine() {
  const python = process.env.XBOX_PYTHON || 'python';
  engine = spawn(python, ['-u', '-m', 'xbox_mode'], {
    cwd: __dirname,
    env: { ...process.env, PYTHONUTF8: '1' },
    stdio: ['pipe', 'pipe', 'inherit'],
    windowsHide: true,
  });
  engine.on('error', (e) => console.error('Failed to start the Python engine:', e.message));
  readline.createInterface({ input: engine.stdout }).on('line', onEngineLine);
}

function onEngineLine(line) {
  let msg;
  try { msg = JSON.parse(line); } catch { return; }
  switch (msg.t) {
    case 'res': {
      const done = pending.get(msg.id);
      pending.delete(msg.id);
      if (done) done(msg.data);
      break;
    }
    case 'btn':
      (msg.target === 'kb' ? kbWin : win)?.webContents.send('btn', msg.name);
      break;
    case 'guide': onGuide(); break;
    case 'toggle_kb': toggleKeyboard(); break;
    case 'pad': padConnected = Boolean(msg.connected); win?.webContents.send('pad', msg.connected); break;
    case 'battery': {
      const was = padBattery;
      padBattery = msg.level;
      win?.webContents.send('battery', msg.level);
      if ((msg.level === 'low' || msg.level === 'empty') && was !== msg.level && Notification.isSupported()) {
        new Notification({
          title: 'Controller battery low',
          body: msg.level === 'empty' ? 'It is almost empty. Plug in a cable or change the batteries.' : 'Plug in a cable or change the batteries soon.',
        }).show();
      }
      break;
    }
    case 'apps_changed': win?.webContents.send('apps-changed'); break;
    case 'guide_long': onGuideLong(); break;
  }
}

async function onGuide() {
  hideKeyboard();
  if (win.isFocused()) {
    win.webContents.send('guide');
    return;
  }
  const prev = await call('foreground');
  win.webContents.send('open-switcher', { prev });
}

// Holding Guide opens quick settings, the way a short press opens the switcher.
async function onGuideLong() {
  hideKeyboard();
  if (win.isFocused()) {
    win.webContents.send('open-quick', { prev: 0 });
    return;
  }
  const prev = await call('foreground');
  win.webContents.send('open-quick', { prev });
}

// ---- windows -----------------------------------------------------------------
function currentDisplay() {
  return screen.getAllDisplays().find((d) => d.id === displayId) || screen.getPrimaryDisplay();
}

function createMainWindow() {
  const d = currentDisplay();
  const b = WINDOWED ? { x: d.bounds.x, y: d.bounds.y, width: 1280, height: 720 } : d.bounds;
  win = new BrowserWindow({
    ...b, frame: false, resizable: false, backgroundColor: '#0b0d12', show: false,
    webPreferences: { preload: path.join(__dirname, 'preload.js'), backgroundThrottling: false },
  });
  win.setMenuBarVisibility(false);
  win.loadFile(path.join('renderer', 'index.html'), { query: { view: VIEW } });
  win.once('ready-to-show', () => {
    win.show();
    uiHwnd = win.getNativeWindowHandle().readUInt32LE(0);
    post({ cmd: 'ui', hwnd: uiHwnd });
    if (!SHOT) post({ cmd: 'apply_taskbar' });
  });
  if (SHOT) {
    win.webContents.on('console-message', (e, ...rest) => console.log('[renderer]', e.message ?? rest[1]));
    win.webContents.once('did-finish-load', () => {
      // Test hook: --press=down:40 replays that many button presses, quickly, before the screenshot.
      const [name, count] = argValue('press').split(':');
      for (let i = 0; name && i < Number(count); i++) {
        setTimeout(() => win.webContents.send('btn', name), 1500 + i * 15);
      }
    });
    win.webContents.once('did-finish-load', () => setTimeout(async () => {
      const img = await win.webContents.capturePage();
      fs.writeFileSync(SHOT, img.toPNG());
      app.quit();
    }, 4000));
  }
  win.on('closed', () => app.quit());
}

function showKeyboard() {
  const d = currentDisplay().bounds;
  const w = Math.round(d.width * 0.62);
  const h = Math.round(d.height * 0.46);
  if (!kbWin) {
    kbWin = new BrowserWindow({
      width: w, height: h, x: d.x + Math.round((d.width - w) / 2), y: d.y + d.height - h - Math.round(d.height * 0.03),
      frame: false, transparent: true, resizable: false, focusable: false, skipTaskbar: true, show: false,
      alwaysOnTop: true, webPreferences: { preload: path.join(__dirname, 'preload.js') },
    });
    kbWin.setAlwaysOnTop(true, 'screen-saver');
    kbWin.loadFile(path.join('renderer', 'keyboard.html'));
    kbWin.once('ready-to-show', () => { kbWin.showInactive(); post({ cmd: 'kb', visible: true }); });
  } else {
    kbWin.showInactive();
    kbWin.webContents.send('reset');
    post({ cmd: 'kb', visible: true });
  }
}

function hideKeyboard() {
  if (kbWin && kbWin.isVisible()) {
    kbWin.hide();
    post({ cmd: 'kb', visible: false });
    win?.webContents.send('kb-closed');
  }
}

function toggleKeyboard() {
  if (kbWin && kbWin.isVisible()) hideKeyboard(); else showKeyboard();
}

// ---- icons / thumbnails --------------------------------------------------------
const iconCache = new Map();
async function iconFor(p) {
  if (iconCache.has(p)) return iconCache.get(p);
  let target = p;
  try {
    if (p.toLowerCase().endsWith('.lnk')) {
      const link = shell.readShortcutLink(p);
      target = link.icon || link.target || p;
    }
  } catch { /* fall back to the path itself */ }
  let url = null;
  try {
    const img = await nativeImage.createThumbnailFromPath(target, { width: 256, height: 256 });
    if (!img.isEmpty()) url = img.toDataURL();
  } catch { /* try the plain file icon */ }
  if (!url) {
    try { url = (await app.getFileIcon(target, { size: 'large' })).toDataURL(); } catch { url = null; }
  }
  iconCache.set(p, url);
  return url;
}

// Keep only shortcuts that open a real program: drop Windows' own tools and non-.exe targets, and duplicates.
const WINDIR = (process.env.WINDIR || 'C:\\Windows').toLowerCase();
function filterApps(list) {
  const seen = new Set();
  return list.filter((a) => {
    if (a.path.startsWith('shell:')) {  // Microsoft Store apps have no shortcut to read
      if (seen.has(a.path)) return false;
      seen.add(a.path);
      return true;
    }
    let target = '';
    try { target = (shell.readShortcutLink(a.path).target || '').toLowerCase(); } catch { return false; }
    if (!target.endsWith('.exe') || target.startsWith(`${WINDIR}\\`) || seen.has(target)) return false;
    seen.add(target);
    if (!canShowWindow(target)) {
      if (SHOT) console.log(`[apps] hidden, console program: ${a.name} -> ${target}`);
      return false;
    }
    return true;
  });
}

ipcMain.handle('engine', async (_e, cmd, extra) => {
  if (cmd === 'launch') {
    // The engine only makes windows of the program you launched full screen, so tell it which executable that is.
    try { extra = { ...extra, exe: path.basename(shell.readShortcutLink(extra.path).target || '') }; } catch { /* unknown */ }
  }
  const data = await call(cmd, extra);
  return cmd === 'apps' ? filterApps(data) : data;
});
ipcMain.handle('icon', (_e, p) => iconFor(p));
ipcMain.handle('thumbs', async (_e, size) => {
  const sources = await desktopCapturer.getSources({
    types: ['window'], thumbnailSize: { width: size.w, height: size.h }, fetchWindowIcons: true,
  });
  return sources.map((s) => ({
    hwnd: Number(s.id.split(':')[1]),
    thumb: s.thumbnail && !s.thumbnail.isEmpty() ? s.thumbnail.toDataURL() : null,
    icon: s.appIcon && !s.appIcon.isEmpty() ? s.appIcon.toDataURL() : null,
  }));
});
ipcMain.handle('selfShot', async () => {
  try {
    const img = await win.webContents.capturePage();
    return img.isEmpty() ? null : img.resize({ width: 640 }).toDataURL();
  } catch { return null; }
});
ipcMain.handle('focusUi', () => post({ cmd: 'focus', hwnd: uiHwnd }));
ipcMain.handle('padState', () => ({ connected: padConnected, battery: padBattery }));
ipcMain.handle('displays', () => {
  const main = screen.getPrimaryDisplay().id;
  const cur = currentDisplay().id;
  return screen.getAllDisplays().map((d, i) => ({
    id: d.id, current: d.id === cur,
    label: `Display ${i + 1}${d.id === main ? ' (main)' : ''}  ${d.bounds.width}x${d.bounds.height}`,
  }));
});
ipcMain.handle('setDisplay', async (_e, id) => {
  displayId = id;
  const b = currentDisplay().bounds;
  win.setBounds(WINDOWED ? { x: b.x, y: b.y, width: 1280, height: 720 } : b);
  if (kbWin) { kbWin.destroy(); kbWin = null; }  // it is rebuilt on the new display the next time it opens
  await call('config_set', { key: 'display_id', value: id });
  return true;
});
ipcMain.handle('kb', (_e, action) => {
  if (action === 'show') showKeyboard();
  else if (action === 'hide') hideKeyboard();
  else toggleKeyboard();
});
ipcMain.handle('quit', () => app.quit());

// ---- lifecycle ---------------------------------------------------------------
// A second copy would start a second engine, and every button press would then be sent twice.
if (!app.requestSingleInstanceLock()) app.quit();

app.whenReady().then(async () => {
  startEngine();
  // The chosen display is part of the engine's config; do not wait for an engine that failed to start.
  const cfg = await Promise.race([call('config_get'), new Promise((r) => setTimeout(() => r({}), 3000))]);
  displayId = cfg.display_id ?? null;
  createMainWindow();
  startBridge({
    getState: () => ({ running: true, version: app.getVersion(), pad: padConnected }),
    onKeyboard: (action) => (action === 'show' ? showKeyboard() : hideKeyboard()),
    onTab: (game) => post({ cmd: 'tab_game', game }),
  });
});

app.on('before-quit', () => {
  post({ cmd: 'quit' });
  setTimeout(() => engine && engine.kill(), 400);
});

app.on('window-all-closed', () => app.quit());
