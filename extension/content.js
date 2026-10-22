// Isolated-world controller. The first pressed button activates the cursor and is consumed.
// Left stick moves the cursor, A clicks or drags, B opens the context menu, right stick scrolls,
// X sends Backspace, Start sends Enter, Y toggles the on-screen keyboard.
(() => {
  const TAG = 'xbox-mode';
  const STICK = { deadzone: 0.12, exponent: 2 };
  const CURSOR_SPEED = 1200;
  const SCROLL_SPEED = 1200;
  const CURSOR_RADIUS = 14;
  const HEARTBEAT_MS = 400;
  const BUTTON = { A: 0, B: 1, X: 2, Y: 3, BACK: 8, START: 9, UP: 12, DOWN: 13, LEFT: 14, RIGHT: 15 };
  const DPAD_KEYS = { [BUTTON.UP]: 'ArrowUp', [BUTTON.DOWN]: 'ArrowDown', [BUTTON.LEFT]: 'ArrowLeft', [BUTTON.RIGHT]: 'ArrowRight' };
  const osk = globalThis.__xboxModeOsk;

  let aware = false;
  let activated = false;
  let latestPad = null;
  let previous = new Set();
  let cursor = { x: window.innerWidth / 2, y: window.innerHeight / 2 };
  let hovered = null;
  let pressedOn = null;
  let dragged = false;
  let lastFrame = 0;

  const overlay = document.createElement('div');
  overlay.id = 'xbox-mode-cursor';
  Object.assign(overlay.style, {
    position: 'fixed',
    left: '0',
    top: '0',
    width: `${CURSOR_RADIUS * 2}px`,
    height: `${CURSOR_RADIUS * 2}px`,
    borderRadius: '50%',
    border: '3px solid #fff',
    boxSizing: 'border-box',
    background: 'rgba(16, 124, 16, 0.4)',
    pointerEvents: 'none',
    zIndex: '2147483647',
    display: 'none',
  });

  window.addEventListener('message', (event) => {
    if (event.source !== window || !event.data || event.data.source !== TAG) return;
    if (event.data.type === 'page-gamepad-aware') aware = true;
    if (event.data.type === 'pads') latestPad = event.data.pads[0] || null;
  });

  function shape(x, y) {
    const magnitude = Math.hypot(x, y);
    if (magnitude <= STICK.deadzone) return [0, 0];
    const scaled = Math.min((magnitude - STICK.deadzone) / (1 - STICK.deadzone), 1);
    const factor = Math.pow(scaled, STICK.exponent) / magnitude;
    return [x * factor, y * factor];
  }

  function showCursor() {
    if (!overlay.isConnected) document.documentElement.appendChild(overlay);
    overlay.style.display = 'block';
    placeCursor();
  }

  function hideCursor() {
    overlay.style.display = 'none';
  }

  function placeCursor() {
    overlay.style.transform = `translate(${cursor.x - CURSOR_RADIUS}px, ${cursor.y - CURSOR_RADIUS}px)`;
  }

  function dispatch(type, el, buttons = 0) {
    if (!el) return;
    const isPointer = type.startsWith('pointer');
    const Ctor = isPointer ? PointerEvent : MouseEvent;
    const bubbles = !/leave|enter/.test(type);
    el.dispatchEvent(
      new Ctor(type, {
        bubbles,
        cancelable: true,
        composed: true,
        view: window,
        clientX: cursor.x,
        clientY: cursor.y,
        button: 0,
        buttons,
        ...(isPointer ? { pointerType: 'mouse', isPrimary: true } : {}),
      }),
    );
  }

  function focusTarget(el) {
    const focusable = el.closest('input, textarea, select, button, a[href], [contenteditable="true"], [tabindex]');
    if (focusable) focusable.focus();
  }

  function updateHover() {
    const el = document.elementFromPoint(cursor.x, cursor.y);
    if (el === hovered) return;
    if (hovered) {
      dispatch('pointerout', hovered);
      dispatch('mouseout', hovered);
      dispatch('mouseleave', hovered);
    }
    hovered = el;
    if (el) {
      dispatch('pointerover', el);
      dispatch('mouseover', el);
      dispatch('mouseenter', el);
    }
    osk.highlight(el);
  }

  function scrollAt(x, y, amount) {
    let node = document.elementFromPoint(x, y);
    while (node && node !== document.body && node !== document.documentElement) {
      const style = getComputedStyle(node);
      if (node.scrollHeight > node.clientHeight + 1 && /(auto|scroll)/.test(style.overflowY)) {
        node.scrollTop += amount;
        return;
      }
      node = node.parentElement;
    }
    window.scrollBy(0, amount);
  }

  function press(index) {
    if (index === BUTTON.A) {
      const key = osk.keyAt(hovered);
      if (key !== null) {
        osk.press(key);
        return;
      }
      pressedOn = hovered;
      dragged = false;
      if (!hovered) return;
      dispatch('pointerdown', hovered, 1);
      dispatch('mousedown', hovered, 1);
      focusTarget(hovered);
    } else if (index === BUTTON.B) {
      dispatch('contextmenu', hovered);
    } else if (index === BUTTON.Y) {
      osk.toggle();
    } else if (index === BUTTON.X) {
      if (!osk.backspace()) sendKey('Backspace');
    } else if (index === BUTTON.START) {
      sendKey('Enter');
    } else if (DPAD_KEYS[index]) {
      sendKey(DPAD_KEYS[index]);
    }
  }

  function release(index) {
    if (index !== BUTTON.A || !pressedOn) return;
    const target = hovered;
    dispatch('pointerup', target);
    dispatch('mouseup', target);
    if (target === pressedOn && !dragged) dispatch('click', target);
    pressedOn = null;
    dragged = false;
  }

  function releaseHeld() {
    if (pressedOn) {
      dispatch('pointerup', hovered);
      dispatch('mouseup', hovered);
    }
    pressedOn = null;
    dragged = false;
  }

  function sendKey(key) {
    const el = document.activeElement || document.body;
    for (const type of ['keydown', 'keyup']) {
      el.dispatchEvent(new KeyboardEvent(type, { key, bubbles: true, cancelable: true }));
    }
  }

  function frame(now) {
    requestAnimationFrame(frame);
    const dt = lastFrame ? Math.min((now - lastFrame) / 1000, 0.1) : 0;
    lastFrame = now;

    const pad = latestPad;
    if (aware || !pad) {
      releaseHeld();
      hideCursor();
      if (aware) activated = false;
      if (!pad) activated = false;
      previous = new Set();
      return;
    }

    const buttons = new Set(pad.buttons.flatMap((down, index) => (down ? [index] : [])));
    const pressed = [...buttons].filter((index) => !previous.has(index));
    const released = [...previous].filter((index) => !buttons.has(index));
    previous = buttons;

    if (!activated) {
      if (pressed.length === 0) return;
      activated = true;
      showCursor();
      return;
    }

    const [lx, ly] = shape(pad.axes[0], pad.axes[1]);
    const [, ry] = shape(pad.axes[2], pad.axes[3]);
    cursor.x = Math.min(Math.max(cursor.x + lx * CURSOR_SPEED * dt, 0), window.innerWidth - 1);
    cursor.y = Math.min(Math.max(cursor.y + ly * CURSOR_SPEED * dt, 0), window.innerHeight - 1);
    placeCursor();
    updateHover();
    if (ry) scrollAt(cursor.x, cursor.y, ry * SCROLL_SPEED * dt);
    if (pressedOn && (lx || ly)) {
      dragged = true;
      dispatch('pointermove', hovered, 1);
      dispatch('mousemove', hovered, 1);
    }
    for (const index of pressed) press(index);
    for (const index of released) release(index);
  }

  setInterval(() => {
    if (document.visibilityState !== 'visible') return;
    const result = chrome.runtime.sendMessage({ type: 'heartbeat', state: aware ? 'native' : 'handling' });
    if (result && result.catch) result.catch(() => {});
  }, HEARTBEAT_MS);

  requestAnimationFrame(frame);
})();
