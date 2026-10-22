// Runs in the page's own JavaScript world. It tells the content script when the page reads gamepads
// itself, and forwards the raw pad state, because the isolated world cannot see page-level overrides.
(() => {
  const TAG = 'xbox-mode';
  const GAMEPAD_EVENTS = new Set(['gamepadconnected', 'gamepaddisconnected']);
  let ownRead = false;
  let announced = false;

  const announce = () => {
    if (announced) return;
    announced = true;
    window.postMessage({ source: TAG, type: 'page-gamepad-aware' }, '*');
  };

  const addListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    if (this === window && GAMEPAD_EVENTS.has(type)) announce();
    return addListener.call(this, type, listener, options);
  };

  const getGamepads = Navigator.prototype.getGamepads;
  Navigator.prototype.getGamepads = function () {
    if (!ownRead) announce();
    return getGamepads.call(this);
  };

  const readPads = () => {
    let pads;
    ownRead = true;
    try {
      pads = navigator.getGamepads();
    } finally {
      ownRead = false;
    }
    const compact = [];
    for (const pad of pads || []) {
      if (!pad) continue;
      compact.push({
        axes: Array.from(pad.axes),
        buttons: Array.from(pad.buttons, (button) => button.pressed),
      });
    }
    window.postMessage({ source: TAG, type: 'pads', pads: compact }, '*');
    requestAnimationFrame(readPads);
  };
  requestAnimationFrame(readPads);
})();
