"""Entry point: wires the controller, outputs, launcher, browser heartbeat and the tick loop."""
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import List, Optional

from .config import load_config
from .engine import Engine
from .gamepad_usage import GamepadUsageCache
from .heartbeat import HeartbeatServer, HeartbeatStore
from .launcher import Launcher
from .launcher_apps import discover_apps, launch
from .outputs import KeyboardOutput, MouseOutput
from .policy import EmulationPolicy
from .system import foreground_process, list_modules, toggle_osk

log = logging.getLogger("xbox_mode")


def _input_backend():
    if sys.platform == "win32":
        from .backend_win import WinInputBackend

        return WinInputBackend()
    from .backend_xtest import XTestBackend

    return XTestBackend()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="xbox_mode")
    parser.add_argument("--config", type=Path, default=Path("config.json"))
    parser.add_argument("--list-apps", action="store_true", help="print discovered apps and exit")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    config = load_config(args.config)
    apps = discover_apps(config["extra_apps"])
    if args.list_apps:
        for app in apps:
            print(app.name)
        return 0

    from .pygame_source import PygameSource

    source = PygameSource(config)
    backend = _input_backend()
    store = HeartbeatStore()
    server = HeartbeatServer(config["heartbeat_port"], store)
    server.start()
    usage = GamepadUsageCache(list_modules, include_dinput=config["detect_dinput"])
    engine = Engine(
        config=config,
        mouse=MouseOutput(backend),
        keyboard=KeyboardOutput(backend),
        launcher=Launcher(apps),
        policy=EmulationPolicy(config["overrides"], config["heartbeat_stale_seconds"]),
        foreground=foreground_process,
        uses_gamepad=usage.check,
        heartbeat=store.latest,
        toggle_osk=toggle_osk,
        launch_app=launch,
    )

    from .launcher_ui import LauncherWindow

    window = LauncherWindow()
    tick = 1.0 / config["tick_rate"]
    log.info("Xbox mode running with %d apps, heartbeat on 127.0.0.1:%d", len(apps), server.port)
    try:
        while True:
            started = time.monotonic()
            try:
                pad = source.read()
                if pad is None:
                    engine.release_all()
                else:
                    engine.step(pad, started)
                window.sync(engine.launcher)
            except Exception:
                log.exception("tick failed")
            time.sleep(max(0.0, tick - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        engine.release_all()
        window.close()
        server.stop()
    return 0
