"""Discovers launchable apps/games from the Start Menu and persists settings and usage."""
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

SKIP = re.compile(r"uninstall|readme|help|licen[cs]e|documentation|release notes|website|manual", re.I)
GAME_HINTS = re.compile(r"steam|epic games|gog|ubisoft|ea app|battle\.net|xbox|minecraft|game", re.I)
DEFAULTS = {"hide_taskbar": True, "mouse_mode": True, "usage": {}}


@dataclass
class App:
    name: str
    path: str


def config_path():
    return Path(os.environ.get("APPDATA", ".")) / "xbox_mode" / "config.json"


def load_config():
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **data}


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
            if SKIP.search(p.stem):
                continue
            seen.setdefault(p.stem.lower(), App(p.stem, str(p)))
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
