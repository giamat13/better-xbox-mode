'use strict';
// Tiny interface sounds made with the Web Audio API, so there are no audio files to ship.
(() => {
  let ctx = null;
  let enabled = true;
  const TONES = {
    move: [[880, 0.025, 0.05]],
    select: [[660, 0.05, 0.1], [990, 0.07, 0.1]],
    back: [[520, 0.05, 0.09], [390, 0.07, 0.09]],
    open: [[520, 0.06, 0.1], [780, 0.06, 0.1], [1040, 0.09, 0.1]],
    alert: [[880, 0.12, 0.14], [660, 0.12, 0.14], [880, 0.18, 0.14]],
  };

  function play(name) {
    if (!enabled || !TONES[name]) return;
    try {
      ctx = ctx || new AudioContext();
      let at = ctx.currentTime;
      for (const [freq, length, gain] of TONES[name]) {
        const osc = ctx.createOscillator();
        const amp = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        amp.gain.setValueAtTime(gain, at);
        amp.gain.exponentialRampToValueAtTime(0.0001, at + length);
        osc.connect(amp).connect(ctx.destination);
        osc.start(at);
        osc.stop(at + length + 0.02);
        at += length * 0.85;
      }
    } catch { /* no audio device: the interface just stays quiet */ }
  }

  window.sfx = { play, enable: (on) => { enabled = Boolean(on); } };
})();
