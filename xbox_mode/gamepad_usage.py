"""Detects whether a process has a controller API loaded, so the app does not compete with it.

The check is generic: any program that reads a controller through XInput, Windows.Gaming.Input
or (optionally) DirectInput loads one of these DLLs, whether it is a known game or not.
"""
from typing import Callable, Dict, Iterable, Optional, Tuple

XINPUT_MODULES = frozenset(
    {"xinput1_1.dll", "xinput1_2.dll", "xinput1_3.dll", "xinput1_4.dll", "xinput9_1_0.dll", "xinputuap.dll"}
)
WGI_MODULES = frozenset({"windows.gaming.input.dll"})
DINPUT_MODULES = frozenset({"dinput8.dll"})


def uses_gamepad_api(module_names: Iterable[str], include_dinput: bool = False) -> bool:
    loaded = {name.lower() for name in module_names}
    wanted = XINPUT_MODULES | WGI_MODULES
    if include_dinput:
        wanted = wanted | DINPUT_MODULES
    return bool(loaded & wanted)


class GamepadUsageCache:
    """Re-reads a process's module list at most once per refresh interval."""

    def __init__(
        self,
        list_modules: Callable[[int], Iterable[str]],
        include_dinput: bool = False,
        refresh_seconds: float = 2.0,
    ) -> None:
        self._list_modules = list_modules
        self._include_dinput = include_dinput
        self._refresh = refresh_seconds
        self._cache: Dict[int, Tuple[float, bool]] = {}

    def check(self, pid: Optional[int], now: float) -> bool:
        if pid is None:
            return False
        cached = self._cache.get(pid)
        if cached is not None and now - cached[0] < self._refresh:
            return cached[1]
        result = uses_gamepad_api(self._list_modules(pid), self._include_dinput)
        self._cache[pid] = (now, result)
        return result
