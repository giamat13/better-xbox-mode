"""Discovers launchable apps/games from the Start Menu and persists settings and usage."""
import copy
import json
import os
import re
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
            "windowless": {}, "has_window": [], "usage": {}}


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


def scan(roots=None):
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
