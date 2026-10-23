'use strict';
// Gamepad-driven on-screen keyboard. It lives in a non-focusable window, so typing goes to the app underneath.
(() => {
const xbox = window.xbox;

const spacer = (w) => ({ label: '', kind: 'spacer', w });
const chars = (s) => [...s].map((label) => ({ label, kind: 'char', w: 1 }));
const special = (label, kind, w = 1) => ({ label, kind, w });

function layout(name) {
  const bottom = [special(name === 'sym' ? 'ABC' : '&123', 'sym', 1.5), special(name === 'en' ? 'עב' : 'EN', 'lang', 1.5),
    special('', 'space', 5), special('◀', 'left'), special('▶', 'right'), special('✕', 'close', 1.5)];
  const digits = [...chars('1234567890'), special('⌫', 'bs', 1.5)];
  const enter = special('⏎', 'enter', 1.5);
  if (name === 'en') {
    return [digits, [spacer(.75), ...chars('qwertyuiop'), spacer(.75)], [...chars("asdfghjkl'"), enter],
      [special('⇧', 'shift', 1.5), ...chars('zxcvbnm,.?')], bottom];
  }
  if (name === 'he') {
    return [digits, [...chars("/'קראטוןםפ"), spacer(1.5)], [...chars('שדגכעיחלךף'), enter],
      [spacer(1.5), ...chars('זסבהנמצתץ.')], bottom];
  }
  return [digits, [spacer(.75), ...chars('!@#$%^&*()'), spacer(.75)], [...chars('-_=+[]{}\\|'), enter],
    [spacer(1.5), ...chars('~`;:"<>/?.')], bottom];
}

const K = { layout: 'en', letters: 'en', shift: false, row: 1, col: 5, rows: [], els: [] };

function build() {
  const host = document.getElementById('rows');
  host.innerHTML = '';
  K.rows = layout(K.layout);
  K.els = K.rows.map((row) => {
    const r = document.createElement('div');
    r.className = 'row';
    const els = row.map((k) => {
      const e = document.createElement('div');
      e.className = `key ${k.kind === 'char' ? '' : k.kind === 'spacer' ? 'spacer' : 'special'}`;
      e.style.flexGrow = k.w;
      r.append(e);
      return e;
    });
    host.append(r);
    return els;
  });
  paint();
}

function paint() {
  K.rows.forEach((row, r) => row.forEach((k, c) => {
    const e = K.els[r][c];
    e.textContent = k.kind === 'char' && K.shift ? k.label.toUpperCase() : k.label;
    e.classList.toggle('focus', r === K.row && c === K.col);
    e.classList.toggle('on', k.kind === 'shift' && K.shift);
  }));
}

const centerX = (r, c) => {
  const b = K.els[r][c].getBoundingClientRect();
  return b.left + b.width / 2;
};

function nearest(r, x) {
  let best = -1, dist = Infinity;
  K.rows[r].forEach((k, c) => {
    if (k.kind === 'spacer') return;
    const d = Math.abs(centerX(r, c) - x);
    if (d < dist) { dist = d; best = c; }
  });
  return best;
}

function stepH(d) {
  let c = K.col + d;
  while (c >= 0 && c < K.rows[K.row].length) {
    if (K.rows[K.row][c].kind !== 'spacer') { K.col = c; return; }
    c += d;
  }
}

function stepV(d) {
  const r = K.row + d;
  if (r < 0 || r >= K.rows.length) return;
  K.col = nearest(r, centerX(K.row, K.col));
  K.row = r;
}

function setLayout(name) {
  const x = centerX(K.row, K.col);
  K.layout = name;
  if (name !== 'sym') K.letters = name;
  build();
  K.col = nearest(K.row, x);
  paint();
}

const type = (text) => xbox.call('type', { text });
const vk = (code) => xbox.call('vk', { code });

function press(k) {
  switch (k.kind) {
    case 'char': type(K.shift ? k.label.toUpperCase() : k.label); K.shift = false; break;
    case 'bs': vk(0x08); break;
    case 'enter': vk(0x0D); break;
    case 'space': type(' '); break;
    case 'left': vk(0x25); break;
    case 'right': vk(0x27); break;
    case 'shift': K.shift = !K.shift; break;
    case 'sym': setLayout(K.layout === 'sym' ? K.letters : 'sym'); break;
    case 'lang': setLayout(K.layout === 'en' ? 'he' : 'en'); break;
    case 'close': xbox.kb('hide'); break;
  }
}

function onButton(name) {
  switch (name) {
    case 'y': case 'guide': return xbox.kb('hide');
    case 'left': stepH(-1); break;
    case 'right': stepH(1); break;
    case 'up': stepV(-1); break;
    case 'down': stepV(1); break;
    case 'a': press(K.rows[K.row][K.col]); break;
    case 'b': vk(0x08); break;
    case 'x': type(' '); break;
    case 'start': vk(0x0D); break;
    case 'lb': vk(0x25); break;
    case 'rb': vk(0x27); break;
  }
  paint();
}

xbox.on('btn', onButton);
xbox.on('reset', () => { K.shift = false; K.layout = K.letters; build(); });
build();
})();
