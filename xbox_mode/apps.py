"""Discovers launchable apps/games from the Start Menu and persists settings and usage."""
import copy
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

SKIP = re.compile(
    r"uninstall|readme|\bhelp\b|licen[cs]e|documentation|release notes|website|manual|\bsetup\b|installer|"
    r"updater|repair|configur|diagnos|migrat", re.I)
# Start Menu folders that only hold system tools, not apps you would launch from a console UI.
FOLDER_SKIP = {"accessories", "administrative tools", "system tools", "windows tools", "windows system",
               "windows powershell", "windows accessories", "windows ease of access", "maintenance", "startup",
               "accessibility"}
GAME_HINTS = re.compile(r"steam|epic games|gog|ubisoft|ea app|battle\.net|xbox|minecraft|game", re.I)
DEFAULTS = {"hide_taskbar": True, "mouse_mode": True, "launch_fullscreen": True, "game_apps": [],
            # Launchers are UIs, not games: they keep the controller-as-mouse even though they load XInput.
            "mouse_apps": ["steam.exe", "steamwebhelper.exe", "EpicGamesLauncher.exe", "Battle.net.exe",
                           "GalaxyClient.exe", "EADesktop.exe", "UbisoftConnect.exe", "upc.exe"], "hidden_apps": [],
            "windowless": {}, "has_window": [], "usage": {}, "run_as_admin": False, "display_id": None,
            "ui_sounds": True, "show_hints": True,
            "favorites": [{"name": "YouTube", "url": "https://www.youtube.com"},
                          {"name": "Google", "url": "https://www.google.com"}]}


@dataclass
class App:
    name: str
    path: str
    folder: str = ""


def config_path():
    return Path(os.environ.get("APPDATA", ".")) / "xbox_mode" / "config.json"


def load_config():
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**copy.deepcopy(DEFAULTS), **data}


def save_config(cfg):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def parse_start_apps(text):
    """Store (UWP) apps from the JSON of PowerShell's Get-StartApps. Desktop programs have no "!" in their id and are
    already found through their Start Menu shortcuts."""
    try:
        data = json.loads(text) if text.strip() else []
    except ValueError:
        return []
    if isinstance(data, dict):
        data = [data]
    found = []
    for d in data:
        name, app_id = d.get("Name", ""), d.get("AppID", "")
        if name and "!" in app_id and not SKIP.search(name):
            found.append(App(name, "shell:AppsFolder\\" + app_id, "Microsoft Store"))
    return found


def scan_store():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                              "Get-StartApps | ConvertTo-Json -Compress"], capture_output=True, timeout=30,
                             creationflags=0x08000000).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError):
        return []
    return parse_start_apps(out)


def known_folders(home=None):
    home = Path(home or os.path.expanduser("~"))
    names = ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos")
    return [{"kind": "folder", "name": n, "path": str(home / n)} for n in names if (home / n).is_dir()]


def recent_files(limit=18, recent_dir=None):
    """The files you opened last, newest first. The shortcut in Windows' Recent folder opens the file itself."""
    root = Path(recent_dir or Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Recent")
    try:
        links = sorted(root.glob("*.lnk"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:  # no such folder, or a drive that is not available
        return []
    links = [p for p in links if not p.stem.lower().startswith("ms-")]  # Windows' own entries (ms-gamingoverlay...)
    return [{"kind": "file", "name": p.stem, "path": str(p)} for p in links[:limit]]


def places(cfg):
    sites = [{"kind": "site", "name": f["name"], "path": f["url"]} for f in cfg.get("favorites", [])]
    return sites + known_folders() + recent_files()


def scan(roots=None, extra=()):
    if roots is None:
        roots = [
            Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
    seen = {}
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*.lnk"):
            parts = p.relative_to(root).parts
            folder = parts[0] if len(parts) > 1 else ""
            if SKIP.search(p.stem) or folder.lower() in FOLDER_SKIP:
                continue
            seen.setdefault(p.stem.lower(), App(p.stem, str(p), folder))
    for app in extra:
        seen.setdefault(app.name.lower(), app)
    return sorted(seen.values(), key=lambda a: a.name.lower())


def recent(apps, cfg, limit=8):
    usage = cfg["usage"]
    used = [a for a in apps if a.path in usage]
    used.sort(key=lambda a: usage[a.path], reverse=True)
    if len(used) < limit:
        extra = [a for a in apps if a.path not in usage and GAME_HINTS.search(a.name)]
        used += extra[: limit - len(used)]
    return used[:limit]


def launch(app, cfg):
    os.startfile(app.path)
    cfg["usage"][app.path] = time.time()
    save_config(cfg)
