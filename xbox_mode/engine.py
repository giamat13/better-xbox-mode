"""Turns one controller snapshot into mouse, keyboard, launcher and on-screen keyboard actions."""
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from .bindings import DEFAULT_BINDINGS, DPAD_KEYS, TOGGLE_CHORD
from .controller import ControllerState
from .launcher import Launcher
from .launcher_apps import App
from .mapping import ButtonEdges, ChordTimer, shape_stick
from .outputs import DpadRepeater, KeyboardOutput, KEY_NAMES, MOUSE_BUTTONS, MouseOutput
from .policy import EmulationPolicy, PageReport

log = logging.getLogger(__name__)

GATE_INTERVAL = 0.25
MAX_STEP_SECONDS = 0.1
ACTION_KINDS = ("mouse", "key", "osk", "launcher")


def _check_binding(button: str, action: str) -> None:
    kind, _, value = action.partition(":")
    if kind not in ACTION_KINDS:
        raise ValueError(f"bindings[{button!r}]: unknown action {action!r}")
    if kind == "mouse" and value not in MOUSE_BUTTONS:
        raise ValueError(f"bindings[{button!r}]: unknown mouse button {value!r}")
    if kind == "key" and value not in KEY_NAMES:
        raise ValueError(f"bindings[{button!r}]: unknown key {value!r}")


class Engine:
    def __init__(
        self,
        config: Dict[str, Any],
        mouse: MouseOutput,
        keyboard: KeyboardOutput,
        launcher: Launcher,
        policy: EmulationPolicy,
        foreground: Callable[[], Tuple[Optional[int], Optional[str]]],
        uses_gamepad: Callable[[Optional[int], float], bool],
        heartbeat: Callable[[], Optional[PageReport]],
        toggle_osk: Callable[[], None],
        launch_app: Callable[[App], None],
    ) -> None:
        self.enabled = True
        self.launcher = launcher
        self._deadzone = config["deadzone"]
        self._exponent = config["stick_exponent"]
        self._mouse_speed = config["mouse_speed"]
        self._scroll_speed = config["scroll_speed"]
        self._bindings = {**DEFAULT_BINDINGS, **config["bindings"]}
        for button, action in self._bindings.items():
            _check_binding(button, action)
        self._mouse = mouse
        self._keyboard = keyboard
        self._policy = policy
        self._foreground = foreground
        self._uses_gamepad = uses_gamepad
        self._heartbeat = heartbeat
        self._toggle_osk = toggle_osk
        self._launch_app = launch_app
        self._edges = ButtonEdges()
        self._chord = ChordTimer(TOGGLE_CHORD, config["toggle_hold_seconds"])
        self._repeat = DpadRepeater(config["dpad_repeat_delay"], config["dpad_repeat_interval"])
        self._last: Optional[float] = None
        self._gate = False
        self._gate_until = float("-inf")

    def release_all(self) -> None:
        self._mouse.release_all()
        self._keyboard.release_all()

    def step(self, pad: ControllerState, now: float) -> None:
        dt = 0.0 if self._last is None else min(max(now - self._last, 0.0), MAX_STEP_SECONDS)
        self._last = now
        pressed, released = self._edges.update(pad.buttons)

        if self._chord.update(pad.buttons, now):
            self.enabled = not self.enabled
            log.info("Xbox mode %s", "on" if self.enabled else "off")
        if "GUIDE" in pressed:
            self.launcher.toggle()

        if self.launcher.open:
            self._launcher_step(pad, pressed, now)
            return
        if not self.enabled or not self._may_emulate(now):
            self.release_all()
            return
        self._emulate(pad, pressed, released, dt, now)

    def _may_emulate(self, now: float) -> bool:
        if now >= self._gate_until:
            pid, exe = self._foreground()
            uses = self._uses_gamepad(pid, now)
            self._gate = self._policy.decide(exe, uses, self._heartbeat(), now)
            self._gate_until = now + GATE_INTERVAL
        return self._gate

    def _launcher_step(self, pad: ControllerState, pressed: frozenset, now: float) -> None:
        self.release_all()
        for dx, dy in self._repeat.update(pad.dpad, now):
            self.launcher.move(dx, dy)
        if "A" in pressed:
            app = self.launcher.select()
            if app is not None:
                self._launch_app(app)
        if "B" in pressed:
            self.launcher.close()

    def _emulate(
        self,
        pad: ControllerState,
        pressed: frozenset,
        released: frozenset,
        dt: float,
        now: float,
    ) -> None:
        dx, dy = shape_stick(pad.left[0], pad.left[1], self._deadzone, self._exponent)
        self._mouse.move(dx * self._mouse_speed * dt, dy * self._mouse_speed * dt)
        _, ry = shape_stick(pad.right[0], pad.right[1], self._deadzone, self._exponent)
        self._mouse.scroll(-ry * self._scroll_speed * dt)
        for name in sorted(pressed):
            self._press(name)
        for name in sorted(released):
            self._release(name)
        for step in self._repeat.update(pad.dpad, now):
            key = DPAD_KEYS.get(step)
            if key is not None:
                self._keyboard.tap(key)

    def _press(self, name: str) -> None:
        kind, _, value = self._bindings.get(name, "").partition(":")
        if kind == "mouse":
            self._mouse.press(value)
        elif kind == "key":
            self._keyboard.tap(value)
        elif kind == "osk":
            self._toggle_osk()

    def _release(self, name: str) -> None:
        kind, _, value = self._bindings.get(name, "").partition(":")
        if kind == "mouse":
            self._mouse.release(value)
