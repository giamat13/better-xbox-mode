'use strict';
// Static check of a Windows executable from its PE headers only (never by name, never by running it).
// The one thing the headers prove reliably is a console program; whether a GUI-subsystem program ever shows a
// window can only be learned by watching it run, which the engine does.
const fs = require('fs');

const IMAGE_SUBSYSTEM_WINDOWS_CUI = 3;

function readSubsystem(file) {
  const fd = fs.openSync(file, 'r');
  try {
    const readAt = (pos, len) => {
      const buf = Buffer.alloc(len);
      return buf.subarray(0, fs.readSync(fd, buf, 0, len, pos));
    };
    const dos = readAt(0, 64);
    if (dos.length < 64 || dos.readUInt16LE(0) !== 0x5a4d) return null;
    const nt = readAt(dos.readUInt32LE(0x3c), 24 + 70);
    if (nt.length < 24 + 70 || nt.readUInt32LE(0) !== 0x4550) return null;
    return nt.readUInt16LE(24 + 68);
  } finally {
    fs.closeSync(fd);
  }
}

/** False only for console programs; anything unreadable or uncertain counts as possibly showing a window. */
function canShowWindow(file) {
  try { return readSubsystem(file) !== IMAGE_SUBSYSTEM_WINDOWS_CUI; } catch { return true; }
}

module.exports = { canShowWindow, readSubsystem };
