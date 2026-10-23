'use strict';
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { canShowWindow, readSubsystem } = require('../pe');

const system32 = path.join(process.env.WINDIR || 'C:\\Windows', 'System32');

test('console programs cannot show a window', () => {
  assert.strictEqual(canShowWindow(path.join(system32, 'cmd.exe')), false);
  assert.strictEqual(canShowWindow(process.execPath), false); // node.exe is a console program
});

test('GUI programs, including launchers that import no UI libraries, are kept', () => {
  assert.strictEqual(canShowWindow(path.join(system32, 'notepad.exe')), true);
  const electron = path.join(__dirname, '..', 'node_modules', 'electron', 'dist', 'electron.exe');
  if (fs.existsSync(electron)) assert.strictEqual(canShowWindow(electron), true);
});

test('unreadable or non-PE files are treated as possibly showing a window', () => {
  assert.strictEqual(canShowWindow(path.join(system32, 'does-not-exist.exe')), true);
  assert.strictEqual(canShowWindow(__filename), true);
  assert.strictEqual(readSubsystem(__filename), null);
});
