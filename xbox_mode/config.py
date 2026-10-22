"""Load config.json on top of built-in defaults and reject values that would misbehave."""
import json
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULTS: Dict[str, Any] = {
    "deadzone": 0.12,
    "stick_exponent": 2.0,
    "mouse_speed": 1400.0,
    "scroll_speed": 12.0,
    "dpad_repeat_delay": 0.4,
    "dpad_repeat_interval": 0.08,
    "tick_rate": 120,
    "toggle_hold_seconds": 1.0,
    "heartbeat_port": 8765,
    "heartbeat_stale_seconds": 1.0,
    "detect_dinput": False,
    "overrides": {},
    "bindings": {},
    "extra_apps": [],
    "joystick_buttons": {
        "A": 0, "B": 1, "X": 2, "Y": 3, "LB": 4, "RB": 5,
        "BACK": 6, "START": 7, "GUIDE": 8, "LS": 9, "RS": 10,
    },
    "joystick_axes": {"left_x": 0, "left_y": 1, "right_x": 2, "right_y": 3, "lt": 4, "rt": 5},
    "joystick_hat": 0,
}

OVERRIDE_VALUES = ("emulate", "pass_through")


def _number(config: Dict[str, Any], key: str, low: float, high: float) -> None:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}, got {value}")


def validate(config: Dict[str, Any]) -> Dict[str, Any]:
    _number(config, "deadzone", 0.0, 0.9)
    _number(config, "stick_exponent", 1.0, 4.0)
    _number(config, "mouse_speed", 1.0, 10000.0)
    _number(config, "scroll_speed", 0.0, 100.0)
    _number(config, "dpad_repeat_delay", 0.05, 2.0)
    _number(config, "dpad_repeat_interval", 0.01, 1.0)
    _number(config, "tick_rate", 10, 1000)
    _number(config, "toggle_hold_seconds", 0.2, 5.0)
    _number(config, "heartbeat_port", 1, 65535)
    _number(config, "heartbeat_stale_seconds", 0.1, 10.0)
    if not isinstance(config["detect_dinput"], bool):
        raise ValueError("detect_dinput must be true or false")
    for exe, mode in config["overrides"].items():
        if mode not in OVERRIDE_VALUES:
            raise ValueError(f"overrides[{exe!r}] must be one of {OVERRIDE_VALUES}")
    for button, action in config["bindings"].items():
        if not isinstance(action, str):
            raise ValueError(f"bindings[{button!r}] must be a string")
    return config


def load_config(path: Optional[Path]) -> Dict[str, Any]:
    config: Dict[str, Any] = json.loads(json.dumps(DEFAULTS))
    if path is None or not path.exists():
        return validate(config)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    unknown = set(loaded) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return validate(config)
