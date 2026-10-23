'use strict';
// Launches Electron with a clean environment. VS Code and other Electron-based hosts export
// ELECTRON_RUN_AS_NODE, which makes Electron behave like plain Node and breaks `require('electron')`.
// When the "Run as administrator" setting is on, it first relaunches itself through UAC, so Xbox Mode can also drive
// windows that run as administrator (Windows ignores injected input aimed at a more privileged window).
const { spawn, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const NO_ELEVATE = '--no-elevate';

function wantsAdmin() {
  try {
    const file = path.join(process.env.APPDATA || '', 'xbox_mode', 'config.json');
    return JSON.parse(fs.readFileSync(file, 'utf8')).run_as_admin === true;
  } catch {
    return false;
  }
}

function isElevated() {
  return spawnSync('fltmc', [], { windowsHide: true }).status === 0;  // only an elevated process may query filters
}

// Returns true when an elevated copy was started and this one has nothing left to do.
function relaunchElevated(args) {
  const quote = (a) => `'${String(a).replace(/'/g, "''")}'`;
  const list = [path.join(__dirname, 'start.js'), ...args, NO_ELEVATE].map(quote).join(',');
  const script = `Start-Process -FilePath ${quote(process.execPath)} -ArgumentList ${list} -WorkingDirectory ${quote(process.cwd())} -Verb RunAs -WindowStyle Hidden`;
  return spawnSync('powershell', ['-NoProfile', '-WindowStyle', 'Hidden', '-Command', script], { stdio: 'inherit', windowsHide: true }).status === 0;
}

const args = process.argv.slice(2).filter((a) => a !== NO_ELEVATE);
const alreadyAsked = process.argv.includes(NO_ELEVATE);

if (process.platform === 'win32' && !alreadyAsked && wantsAdmin() && !isElevated() && relaunchElevated(args)) {
  process.exit(0);
}

const electron = require('electron');
const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

const child = spawn(electron, ['.', ...args], { stdio: 'inherit', env });
child.on('exit', (code) => process.exit(code ?? 0));
