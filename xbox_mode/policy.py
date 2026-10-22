"""Decides whether the controller should drive mouse and keyboard right now."""
from dataclasses import dataclass
from typing import Dict, Optional

BROWSERS = frozenset({"chrome.exe", "msedge.exe", "brave.exe"})
HANDLING = "handling"  # the Chrome extension emulates input on this page
NATIVE = "native"  # the page reads the gamepad itself, so nothing is emulated
RELEASED = "released"  # the cursor was pushed off the page, so the desktop app moves the real mouse


@dataclass(frozen=True)
class PageReport:
    state: str
    received_at: float


class EmulationPolicy:
    def __init__(self, overrides: Dict[str, str], stale_after: float) -> None:
        self._overrides = {exe.lower(): mode for exe, mode in overrides.items()}
        self._stale_after = stale_after

    def decide(
        self,
        exe: Optional[str],
        uses_gamepad: bool,
        report: Optional[PageReport],
        now: float,
    ) -> bool:
        name = (exe or "").lower()
        override = self._overrides.get(name)
        if override is not None:
            return override == "emulate"
        if name in BROWSERS:
            fresh = report is not None and now - report.received_at <= self._stale_after
            if fresh and report.state in (HANDLING, NATIVE):
                return False
            return True
        return not uses_gamepad
