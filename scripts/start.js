'use strict';
// Launches Electron with a clean environment. VS Code and other Electron-based hosts export
// ELECTRON_RUN_AS_NODE, which makes Electron behave like plain Node and breaks `require('electron')`.
const { spawn } = require('child_process');
const electron = require('electron');

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

const child = spawn(electron, ['.', ...process.argv.slice(2)], { stdio: 'inherit', env });
child.on('exit', (code) => process.exit(code ?? 0));
