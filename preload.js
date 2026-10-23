'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('xbox', {
  call: (cmd, extra) => ipcRenderer.invoke('engine', cmd, extra || {}),
  icon: (p) => ipcRenderer.invoke('icon', p),
  thumbs: (size) => ipcRenderer.invoke('thumbs', size),
  selfShot: () => ipcRenderer.invoke('selfShot'),
  focusUi: () => ipcRenderer.invoke('focusUi'),
  padState: () => ipcRenderer.invoke('padState'),
  displays: () => ipcRenderer.invoke('displays'),
  setDisplay: (id) => ipcRenderer.invoke('setDisplay', id),
  kb: (action) => ipcRenderer.invoke('kb', action),
  quit: () => ipcRenderer.invoke('quit'),
  on: (channel, cb) => ipcRenderer.on(channel, (_e, data) => cb(data)),
});
