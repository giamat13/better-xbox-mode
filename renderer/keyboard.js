'use strict';
// Gamepad-driven on-screen keyboard. It lives in a non-focusable window, so typing goes to the app underneath.
// Layers: English, Hebrew, symbols, shortcuts (sticky Ctrl/Alt/Win/Shift, copy/paste/undo, dictation, clipboard history)
// and emoji. The letter layers show word suggestions above the keys.
(() => {
const xbox = window.xbox;

const VK = { bs: 0x08, tab: 0x09, enter: 0x0D, shift: 0x10, ctrl: 0x11, alt: 0x12, esc: 0x1B, pgup: 0x21, pgdn: 0x22,
  end: 0x23, home: 0x24, left: 0x25, up: 0x26, right: 0x27, down: 0x28, del: 0x2E, win: 0x5B, period: 0xBE, f4: 0x73,
  f5: 0x74 };
const MODS = ['ctrl', 'alt', 'win', 'shift'];
const MOD_LABEL = { ctrl: 'Ctrl', alt: 'Alt', win: 'Win', shift: '⇧ Shift' };
const letter = (c) => c.charCodeAt(0);

const spacer = (w) => ({ label: '', kind: 'spacer', w });
const chars = (s) => [...s].map((label) => ({ label, kind: 'char', w: 1 }));
const emojis = (s) => [...s.split(' ')].map((label) => ({ label, kind: 'emoji', w: 1 }));
const special = (label, kind, w = 1) => ({ label, kind, w });
const combo = (label, keys, w = 1) => ({ label, kind: 'combo', keys, w });
const vkey = (label, code, w = 1) => ({ label, kind: 'vkey', code, w });
const mod = (name, w = 1) => ({ label: MOD_LABEL[name], kind: 'mod', mod: name, w });

const EMOJI_ROWS = [
  '😀 😂 🤣 😊 😍 😘 😎 🤔 😢 😭', '😡 👍 👎 👏 🙏 💪 🎉 🔥 ❤️ 💔', '✨ ⭐ 🎮 🎧 📷 💻 📱 🚀 ✅ ❌', '⚠️ 💯 😴 🤝 👋 🙌 😅 😉 🥳 😇',
];

function layout(name) {
  const bottom = [special(name === 'sym' ? 'ABC' : '&123', 'sym', 1.3), special(name === 'en' ? 'עב' : 'EN', 'lang', 1.3),
    special('🎤', 'dictate'), special('😀', 'emojis'), special('', 'space', 3), special('◀', 'left'), special('▶', 'right'),
    special('⌘', 'cmd', 1.3), special('✕', 'close', 1.3)];
  const digits = [...chars('1234567890'), special('⌫', 'bs', 1.5)];
  const enter = special('⏎', 'enter', 1.5);
  const sugs = [special('', 'sug', 3), special('', 'sug', 3), special('', 'sug', 3)];
  if (name === 'en') {
    return [sugs, digits, [spacer(.75), ...chars('qwertyuiop'), spacer(.75)], [...chars("asdfghjkl'"), enter],
      [special('⇧', 'shift', 1.5), ...chars('zxcvbnm,.?')], bottom];
  }
  if (name === 'he') {
    return [sugs, digits, [...chars("/'קראטוןםפ"), spacer(1.5)], [...chars('שדגכעיחלךף'), enter],
      [spacer(1.5), ...chars('זסבהנמצתץ.')], bottom];
  }
  if (name === 'cmd') {
    return [
      [...MODS.map((m) => mod(m)), vkey('Tab', VK.tab), vkey('Esc', VK.esc), vkey('Del', VK.del)],
      [combo('Copy', [VK.ctrl, letter('C')]), combo('Paste', [VK.ctrl, letter('V')]), combo('Cut', [VK.ctrl, letter('X')]),
        combo('Undo', [VK.ctrl, letter('Z')]), combo('Redo', [VK.ctrl, letter('Y')]), combo('Select all', [VK.ctrl, letter('A')]),
        combo('Save', [VK.ctrl, letter('S')])],
      [combo('Close', [VK.alt, VK.f4]), vkey('Refresh', VK.f5), combo('Find', [VK.ctrl, letter('F')]),
        combo('Switch', [VK.alt, VK.tab]), combo('Desktop', [VK.win, letter('D')]), combo('🎤 Dictate', [VK.win, letter('H')]),
        combo('📋 Clipboard', [VK.win, letter('V')])],
      [vkey('▲', VK.up), vkey('▼', VK.down), vkey('◀', VK.left), vkey('▶', VK.right), vkey('Home', VK.home), vkey('End', VK.end),
        vkey('PgUp', VK.pgup), vkey('PgDn', VK.pgdn)],
      [special('ABC', 'sym', 1.5), combo('Emoji panel', [VK.win, VK.period], 2), special('⌫', 'bs'), special('⏎', 'enter'),
        special('', 'space', 3), special('✕', 'close', 1.3)],
    ];
  }
  if (name === 'emoji') {
    return [...EMOJI_ROWS.map((r) => emojis(r)), [special('ABC', 'sym', 1.5), special('⌫', 'bs'), special('', 'space', 4),
      special('⏎', 'enter'), special('✕', 'close', 1.5)]];
  }
  return [digits, [spacer(.75), ...chars('!@#$%^&*()'), spacer(.75)], [...chars('-_=+[]{}\\|'), enter],
    [spacer(1.5), ...chars('~`;:"<>/?.')], bottom];
}

const K = { layout: 'en', letters: 'en', shift: false, ctrl: false, alt: false, win: false, word: '', sugs: [], row: 2, col: 5,
  rows: [], els: [] };

// ---- word suggestions --------------------------------------------------------------------------
const LEARN_KEY = 'xb_words';
const LEARN_MAX = 2000;
let learned = {};
try { learned = JSON.parse(localStorage.getItem(LEARN_KEY) || '{}'); } catch { learned = {}; }

function learn(word) {
  if ([...word].length < 3) return;
  learned[word.toLowerCase()] = (learned[word.toLowerCase()] || 0) + 1;
  const keys = Object.keys(learned);
  if (keys.length > LEARN_MAX) {  // forget the words seen least
    keys.sort((a, b) => learned[a] - learned[b]).slice(0, keys.length - LEARN_MAX).forEach((k) => delete learned[k]);
  }
  try { localStorage.setItem(LEARN_KEY, JSON.stringify(learned)); } catch { /* storage is optional */ }
}

function suggest(prefix, lang) {
  const p = prefix.toLowerCase();
  if (!p) return [];
  const mine = Object.keys(learned).filter((w) => w.startsWith(p) && w !== p && (lang === 'he') === /[֐-׿]/.test(w))
    .sort((a, b) => learned[b] - learned[a]);
  const base = (window.WORDS[lang] || []).filter((w) => w.startsWith(p) && w !== p);
  const out = [...new Set([...mine, ...base])].slice(0, 3);
  const cap = prefix[0] !== prefix[0].toLowerCase();  // typed a capital: suggest a capitalised word
  return out.map((w) => (cap ? w[0].toUpperCase() + w.slice(1) : w));
}

function refreshSuggestions() {
  K.sugs = K.layout === 'en' || K.layout === 'he' ? suggest(K.word, K.layout) : [];
}

function trackChar(ch) {
  if (/\s/.test(ch)) endWord(); else K.word += ch;
}

function endWord() {
  if (K.word) learn(K.word);
  K.word = '';
}

function trackBackspace() {
  K.word = [...K.word].slice(0, -1).join('');
}

// ---- layout ------------------------------------------------------------------------------------
function build() {
  const host = document.getElementById('rows');
  host.innerHTML = '';
  K.rows = layout(K.layout);
  K.els = K.rows.map((row) => {
    const r = document.createElement('div');
    r.className = 'row';
    const els = row.map((k) => {
      const e = document.createElement('div');
      e.className = `key ${k.kind === 'char' || k.kind === 'emoji' ? '' : k.kind === 'spacer' ? 'spacer' : 'special'}`;
      e.style.flexGrow = k.w;
      r.append(e);
      return e;
    });
    host.append(r);
    return els;
  });
  paint();
}

function labelOf(k, c) {
  if (k.kind === 'sug') return K.sugs[c] || '';
  if (k.kind === 'char') return K.shift ? k.label.toUpperCase() : k.label;
  return k.label;
}

function isOn(k) {
  return (k.kind === 'shift' && K.shift) || (k.kind === 'mod' && K[k.mod]);
}

function paint() {
  K.rows.forEach((row, r) => row.forEach((k, c) => {
    const e = K.els[r][c];
    const text = labelOf(k, c);
    e.textContent = text;
    e.classList.toggle('focus', r === K.row && c === K.col);
    e.classList.toggle('on', isOn(k));
    e.classList.toggle('small', [...text].length > 2 && k.kind !== 'sug');
    e.classList.toggle('sug', k.kind === 'sug');
    e.classList.toggle('empty', k.kind === 'sug' && !text);
  }));
  const mods = MODS.filter((m) => K[m] && (m !== 'shift' || K.ctrl || K.alt || K.win)).map((m) => MOD_LABEL[m]);
  document.getElementById('mods').textContent = mods.length ? `${mods.join(' + ')} + …` : '';
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

const startRow = (name) => (name === 'en' || name === 'he' ? 2 : 1);

// home: start at the top-left key (the shortcuts and emoji layers), instead of the key that happens to sit under the old one.
function setLayout(name, home = false) {
  const x = centerX(K.row, K.col);
  K.layout = name;
  if (name === 'en' || name === 'he') K.letters = name;
  refreshSuggestions();
  build();
  K.row = Math.min(K.row, K.rows.length - 1);
  if (K.rows[K.row].every((k) => k.kind === 'spacer')) K.row = startRow(name);
  if (K.layout !== 'en' && K.layout !== 'he' && K.row === 0 && K.rows[0].some((k) => k.kind === 'sug')) K.row = 1;
  K.col = nearest(K.row, x);
  if (home) { K.row = 0; K.col = 0; }
  paint();
}

// ---- sending keys ----------------------------------------------------------------------------
const type = (text) => xbox.call('type', { text });
const vk = (code, times = 1) => xbox.call('vk', { code, times });
const chord = (keys) => xbox.call('chord', { keys });

// Held modifiers apply to the next key only, then let go.
function heldMods() {
  const mods = [];
  if (K.ctrl) mods.push(VK.ctrl);
  if (K.alt) mods.push(VK.alt);
  if (K.win) mods.push(VK.win);
  if (mods.length && K.shift) mods.push(VK.shift);
  return mods;
}

function clearMods() {
  K.ctrl = K.alt = K.win = false;
  K.shift = false;
}

// Sends a key (virtual-key code or a character), as a chord if modifiers are held. Returns true when it did.
function keyWithMods(key) {
  const mods = heldMods();
  if (!mods.length) return false;
  chord([...mods, typeof key === 'string' ? key.toLowerCase() : key]);
  clearMods();
  endWord();
  return true;
}

function acceptSuggestion(word) {
  vk(VK.bs, [...K.word].length);
  type(`${word} `);
  learn(word);
  K.word = '';
}

function press(k, c) {
  switch (k.kind) {
    case 'char': {
      if (keyWithMods(k.label)) break;
      const ch = K.shift ? k.label.toUpperCase() : k.label;
      type(ch);
      trackChar(ch);
      K.shift = false;
      break;
    }
    case 'emoji': type(k.label); endWord(); break;
    case 'bs': if (!keyWithMods(VK.bs)) { vk(VK.bs); trackBackspace(); } break;
    case 'enter': if (!keyWithMods(VK.enter)) { vk(VK.enter); endWord(); } break;
    case 'space': if (!keyWithMods(' ')) { type(' '); endWord(); } break;
    case 'left': if (!keyWithMods(VK.left)) { vk(VK.left); endWord(); } break;
    case 'right': if (!keyWithMods(VK.right)) { vk(VK.right); endWord(); } break;
    case 'vkey': if (!keyWithMods(k.code)) { vk(k.code); endWord(); } break;
    case 'combo': chord(k.keys); clearMods(); endWord(); break;
    case 'mod': K[k.mod] = !K[k.mod]; break;
    case 'shift': K.shift = !K.shift; break;
    case 'sug': if (K.sugs[c]) acceptSuggestion(K.sugs[c]); break;
    case 'dictate': chord([VK.win, letter('H')]); endWord(); break;
    case 'sym': setLayout(K.layout === 'sym' || K.layout === 'cmd' || K.layout === 'emoji' ? K.letters : 'sym'); return;
    case 'cmd': setLayout('cmd', true); return;
    case 'emojis': setLayout('emoji', true); return;
    case 'lang': setLayout(K.layout === 'en' ? 'he' : 'en'); return;
    case 'close': xbox.kb('hide'); return;
  }
  refreshSuggestions();
}

function onButton(name) {
  const here = K.rows[K.row][K.col];
  switch (name) {
    case 'y': case 'guide': return xbox.kb('hide');
    case 'left': stepH(-1); break;
    case 'right': stepH(1); break;
    case 'up': stepV(-1); break;
    case 'down': stepV(1); break;
    case 'a': press(here, K.col); break;
    case 'b': if (!keyWithMods(VK.bs)) { vk(VK.bs); trackBackspace(); } refreshSuggestions(); break;
    case 'x': if (!keyWithMods(' ')) { type(' '); endWord(); } refreshSuggestions(); break;
    case 'start': if (!keyWithMods(VK.enter)) { vk(VK.enter); endWord(); } refreshSuggestions(); break;
    case 'lb': vk(VK.left); endWord(); refreshSuggestions(); break;
    case 'rb': vk(VK.right); endWord(); refreshSuggestions(); break;
  }
  paint();
}

xbox.on('btn', onButton);
xbox.on('reset', () => {
  K.shift = K.ctrl = K.alt = K.win = false;
  K.word = '';
  K.layout = K.letters;
  K.row = startRow(K.layout);
  K.col = 5;
  refreshSuggestions();
  build();
});
build();
})();
