"""Finds launchable apps: Start Menu shortcuts on Windows, desktop entries on Linux."""
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

SHORTCUT_SUFFIXES = (".lnk", ".url")
FIELD_CODE = re.compile(r"%[fFuUdDnNickvm]")


@dataclass(frozen=True)
class App:
    name: str
    path: Optional[str] = None
    command: Optional[Sequence[str]] = None


def windows_start_menu_roots() -> List[Path]:
    roots = []
    for variable in ("APPDATA", "PROGRAMDATA"):
        base = os.environ.get(variable)
        if base:
            roots.append(Path(base, "Microsoft", "Windows", "Start Menu", "Programs"))
    return roots


def linux_desktop_roots() -> List[Path]:
    return [Path("/usr/share/applications"), Path.home() / ".local" / "share" / "applications"]


def discover_windows(roots: Iterable[Path]) -> List[App]:
    found: Dict[str, App] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.suffix.lower() not in SHORTCUT_SUFFIXES or not path.is_file():
                continue
            if "uninstall" in path.stem.lower():
                continue
            found.setdefault(path.stem.lower(), App(name=path.stem, path=str(path)))
    return sorted(found.values(), key=lambda app: app.name.lower())


def parse_desktop_entry(text: str) -> Optional[Dict[str, Any]]:
    values: Dict[str, str] = {}
    in_entry = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_entry = line == "[Desktop Entry]"
            continue
        if in_entry and "=" in line:
            key, _, value = line.partition("=")
            values.setdefault(key.strip(), value.strip())
    if values.get("Type") != "Application":
        return None
    if values.get("NoDisplay") == "true" or values.get("Hidden") == "true":
        return None
    name, exec_line = values.get("Name"), values.get("Exec")
    if not name or not exec_line:
        return None
    cleaned = FIELD_CODE.sub("", exec_line.replace("%%", "\0")).replace("\0", "%")
    try:
        command = shlex.split(cleaned)
    except ValueError:
        return None
    return {"name": name, "command": command} if command else None


def discover_linux(roots: Iterable[Path]) -> List[App]:
    found: Dict[str, App] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.desktop"):
            entry = parse_desktop_entry(path.read_text(encoding="utf-8", errors="replace"))
            if entry is not None:
                found.setdefault(entry["name"].lower(), App(name=entry["name"], command=tuple(entry["command"])))
    return sorted(found.values(), key=lambda app: app.name.lower())


def extra_apps(entries: Iterable[Dict[str, Any]]) -> List[App]:
    apps = []
    for entry in entries:
        command = tuple(shlex.split(entry["command"])) if "command" in entry else None
        apps.append(App(name=entry["name"], path=entry.get("path"), command=command))
    return apps


def discover_apps(extra: Iterable[Dict[str, Any]], windows: Optional[bool] = None) -> List[App]:
    use_windows = sys.platform == "win32" if windows is None else windows
    base = discover_windows(windows_start_menu_roots()) if use_windows else discover_linux(linux_desktop_roots())
    merged: Dict[str, App] = {app.name.lower(): app for app in base}
    for app in extra_apps(extra):
        merged[app.name.lower()] = app
    return sorted(merged.values(), key=lambda app: app.name.lower())


def launch(app: App) -> None:
    if app.path is not None:
        os.startfile(app.path)  # type: ignore[attr-defined]  # Windows only; resolves .lnk targets
        return
    if app.command:
        subprocess.Popen(list(app.command), start_new_session=True)
