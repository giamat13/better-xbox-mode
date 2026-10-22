"""Reads the first connected controller through pygame and converts it to ControllerState."""
import time
from typing import Any, Dict, Optional

from .controller import ControllerState

RECONNECT_SECONDS = 1.0


class PygameSource:
    def __init__(self, config: Dict[str, Any]) -> None:
        import pygame  # imported lazily so the rest of the package runs without pygame

        self._pygame = pygame
        pygame.init()
        pygame.joystick.init()
        self._config = config
        self._joystick = None
        self._next_attempt = 0.0

    def _open(self, now: float):
        if self._joystick is not None:
            return self._joystick
        if now < self._next_attempt:
            return None
        self._next_attempt = now + RECONNECT_SECONDS
        if self._pygame.joystick.get_count() == 0:
            return None
        joystick = self._pygame.joystick.Joystick(0)
        joystick.init()
        self._joystick = joystick
        return joystick

    def read(self) -> Optional[ControllerState]:
        self._pygame.event.pump()
        joystick = self._open(time.monotonic())
        if joystick is None:
            return None
        try:
            return self._snapshot(joystick)
        except self._pygame.error:
            self._joystick = None
            return None

    def _snapshot(self, joystick) -> ControllerState:
        axes = self._config["joystick_axes"]
        buttons = self._config["joystick_buttons"]

        def axis(index: int) -> float:
            return joystick.get_axis(index) if index < joystick.get_numaxes() else 0.0

        def trigger(index: int) -> float:
            return min(max((axis(index) + 1.0) / 2.0, 0.0), 1.0)

        pressed = frozenset(
            name
            for name, index in buttons.items()
            if index < joystick.get_numbuttons() and joystick.get_button(index)
        )
        hat = self._config["joystick_hat"]
        hat_x, hat_y = joystick.get_hat(hat) if hat < joystick.get_numhats() else (0, 0)
        return ControllerState(
            left=(axis(axes["left_x"]), axis(axes["left_y"])),
            right=(axis(axes["right_x"]), axis(axes["right_y"])),
            lt=trigger(axes["lt"]),
            rt=trigger(axes["rt"]),
            buttons=pressed,
            dpad=(hat_x, -hat_y),
        )
