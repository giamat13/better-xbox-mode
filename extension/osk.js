// On-screen keyboard for pages without gamepad support. Y opens it for the focused text field.
(() => {
  const ROWS = ['1234567890', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm'];
  const KEY_ATTRIBUTE = 'data-xbox-osk-key';
  const TEXT_INPUT_TYPES = /^(text|search|url|tel|email|password|number)$/i;
  let root = null;
  let target = null;
  let lastEditable = null;
  let highlighted = null;

  function isEditable(el) {
    if (!el) return false;
    if (el.isContentEditable) return true;
    if (el.tagName === 'TEXTAREA') return true;
    return el.tagName === 'INPUT' && TEXT_INPUT_TYPES.test(el.type || 'text');
  }

  document.addEventListener(
    'focusin',
    (event) => {
      if (isEditable(event.target)) lastEditable = event.target;
    },
    true,
  );

  function keyCell(key, label) {
    const cell = document.createElement('span');
    cell.setAttribute(KEY_ATTRIBUTE, key);
    cell.textContent = label;
    Object.assign(cell.style, {
      display: 'inline-block',
      minWidth: '44px',
      padding: '10px 12px',
      margin: '3px',
      borderRadius: '6px',
      background: '#333',
    });
    if (key === ' ') cell.style.minWidth = '260px';
    if (key === 'Backspace' || key === 'Enter') cell.style.minWidth = '120px';
    return cell;
  }

  function build() {
    root = document.createElement('div');
    root.id = 'xbox-mode-osk';
    Object.assign(root.style, {
      position: 'fixed',
      left: '0',
      right: '0',
      bottom: '0',
      zIndex: '2147483646',
      display: 'none',
      padding: '10px',
      background: '#1e1e1e',
      color: '#fff',
      font: '18px system-ui, sans-serif',
      textAlign: 'center',
      boxSizing: 'border-box',
    });
    for (const row of ROWS) {
      const line = document.createElement('div');
      for (const char of row) line.appendChild(keyCell(char, char));
      root.appendChild(line);
    }
    const bottom = document.createElement('div');
    bottom.appendChild(keyCell('Backspace', '⌫'));
    bottom.appendChild(keyCell(' ', 'space'));
    bottom.appendChild(keyCell('Enter', 'Enter'));
    root.appendChild(bottom);
    document.documentElement.appendChild(root);
  }

  function isOpen() {
    return root !== null && root.style.display !== 'none';
  }

  function open() {
    const candidate = isEditable(document.activeElement) ? document.activeElement : lastEditable;
    if (!candidate || !candidate.isConnected) return false;
    target = candidate;
    if (!root) build();
    root.style.display = 'block';
    return true;
  }

  function close() {
    if (root) root.style.display = 'none';
    target = null;
    highlight(null);
  }

  function toggle() {
    if (isOpen()) close();
    else open();
  }

  function keyAt(el) {
    if (!isOpen() || !el) return null;
    const cell = el.closest(`[${KEY_ATTRIBUTE}]`);
    return cell ? cell.getAttribute(KEY_ATTRIBUTE) : null;
  }

  function highlight(el) {
    const cell = el && isOpen() ? el.closest(`[${KEY_ATTRIBUTE}]`) : null;
    if (cell === highlighted) return;
    if (highlighted) highlighted.style.background = '#333';
    highlighted = cell;
    if (highlighted) highlighted.style.background = '#107c10';
  }

  function insertText(el, text) {
    el.focus();
    if (el.isContentEditable) {
      document.execCommand('insertText', false, text);
      return;
    }
    if (el.selectionStart === null) {
      el.value += text;
    } else {
      el.setRangeText(text, el.selectionStart, el.selectionEnd, 'end');
    }
    el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text, inputType: 'insertText' }));
  }

  function deleteBack(el) {
    el.focus();
    if (el.isContentEditable) {
      document.execCommand('delete');
      return;
    }
    if (el.selectionStart === null) {
      el.value = el.value.slice(0, -1);
    } else {
      const end = el.selectionEnd;
      const start = el.selectionStart === end ? Math.max(0, end - 1) : el.selectionStart;
      el.setRangeText('', start, end, 'end');
    }
    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward' }));
  }

  function backspace() {
    const el = document.activeElement;
    if (!isEditable(el)) return false;
    deleteBack(el);
    return true;
  }

  function press(key) {
    if (!target || !target.isConnected) {
      close();
      return;
    }
    if (key === 'Backspace') deleteBack(target);
    else if (key === 'Enter') {
      if (target.tagName === 'TEXTAREA' || target.isContentEditable) insertText(target, '\n');
    } else insertText(target, key);
  }

  globalThis.__xboxModeOsk = { toggle, isOpen, keyAt, press, highlight, close, backspace };
})();
