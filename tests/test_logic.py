import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from unittest import mock

from xbox_mode import apps, winman
from xbox_mode.engine import Engine
from xbox_mode.xinput import Pad


def gamepad(buttons=0, lx=0, ly=0):
    return SimpleNamespace(wButtons=buttons, bLeftTrigger=0, bRightTrigger=0, sThumbLX=lx, sThumbLY=ly,
                           sThumbRX=0, sThumbRY=0)


class IsolatedConfig(unittest.TestCase):
    """Tests must never read or write the real %APPDATA%\\xbox_mode\\config.json."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(apps, "config_path", return_value=Path(tmp.name) / "config.json")
        patch.start()
        self.addCleanup(patch.stop)


class PadTests(unittest.TestCase):
    def pad_with(self, frames):
        pad = Pad()
        it = iter(frames)
        pad._read = lambda: next(it)
        return pad

    def test_deadzone_and_full_deflection(self):
        self.assertEqual(Pad._norm(0), 0.0)
        self.assertEqual(Pad._norm(3000), 0.0)
        self.assertAlmostEqual(Pad._norm(32767), 1.0)
        self.assertAlmostEqual(Pad._norm(-32768), -1.0)

    def test_stick_emits_direction_events_for_menus(self):
        pad = self.pad_with([gamepad(lx=32000)])
        pad.update(0.0)
        self.assertEqual(pad.nav, ["right"])

    def test_stick_does_not_press_arrows_while_it_drives_the_mouse(self):
        pad = self.pad_with([gamepad(lx=32000)])
        pad.stick_nav = False
        pad.update(0.0)
        self.assertEqual(pad.nav, [])
        self.assertGreater(pad.lx, 0.9)

    def test_dpad_repeats_after_delay_only(self):
        pad = self.pad_with([gamepad(buttons=0x0001)] * 3)
        pad.update(0.0)
        self.assertEqual(pad.nav, ["up"])
        pad.update(0.1)
        self.assertEqual(pad.nav, [])
        pad.update(0.5)
        self.assertEqual(pad.nav, ["up"])

    def test_button_edges(self):
        pad = self.pad_with([gamepad(buttons=0x1000), gamepad(buttons=0x1000), gamepad(buttons=0)])
        pad.update(0.0)
        self.assertEqual(pad.pressed, {"a"})
        pad.update(0.01)
        self.assertEqual(pad.pressed, set())
        pad.update(0.02)
        self.assertEqual(pad.released, {"a"})

    def test_guide_bit(self):
        pad = self.pad_with([gamepad(buttons=0x0400)])
        pad.update(0.0)
        self.assertIn("guide", pad.pressed)


class FullscreenPlanTests(unittest.TestCase):
    MONITOR = (0, 0, 1920, 1080)
    NORMAL = winman.WS_CAPTION | winman.WS_THICKFRAME | 0x10000000  # a regular resizable window

    def plan(self, style=NORMAL, rect=(100, 100, 1100, 800), monitor=MONITOR, cls="Chrome_WidgetWin_1"):
        return winman.fullscreen_plan(cls, style, rect, monitor)

    def test_regular_window_becomes_borderless_and_monitor_sized(self):
        style, box = self.plan()
        self.assertEqual(style & (winman.WS_CAPTION | winman.WS_THICKFRAME), 0)
        self.assertEqual(box, (0, 0, 1920, 1080))

    def test_uses_the_monitor_the_window_is_on(self):
        self.assertEqual(self.plan(rect=(2000, 50, 3000, 700), monitor=(1920, 0, 5760, 2160))[1], (1920, 0, 3840, 2160))

    def test_window_that_is_already_full_screen_is_left_alone(self):
        borderless = winman.WS_THICKFRAME | 0x10000000
        self.assertIsNone(self.plan(style=borderless, rect=(0, 0, 1920, 1080)))

    def test_maximized_window_with_a_title_bar_loses_the_bars_without_shrinking(self):
        style, box = self.plan(rect=(-8, -8, 1928, 1088))
        self.assertEqual(style & winman.WS_CAPTION, 0)
        self.assertEqual(box, (0, 0, 1920, 1080))

    def test_dialogs_fixed_size_and_small_windows_are_left_alone(self):
        self.assertIsNone(self.plan(cls="#32770"))
        self.assertIsNone(self.plan(style=winman.WS_CAPTION))
        self.assertIsNone(self.plan(rect=(0, 0, 300, 200)))


class GameDetectionTests(IsolatedConfig):
    def make(self, exe="game.exe", covers=True, modules=frozenset(), exclusive=False, **cfg):
        engine = Engine()
        engine.cfg.update({"game_apps": [], "mouse_apps": [], **cfg})
        engine.exclusive = exclusive
        engine.next_exclusive_check = 10 ** 9  # never ask the shell during a test
        patches = [mock.patch.object(winman, "exe_name", return_value=exe),
                   mock.patch.object(winman, "covers_screen", return_value=covers),
                   mock.patch.object(winman, "pid_of", return_value=1),
                   mock.patch.object(winman, "module_names", return_value=modules)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return engine

    def test_full_screen_app_that_loaded_xinput_keeps_the_controller(self):
        self.assertTrue(self.make(modules={"xinput1_4.dll", "kernel32.dll"}).is_game(99, 0.0))

    def test_full_screen_app_without_a_gamepad_library_gets_the_mouse(self):
        self.assertFalse(self.make(modules={"kernel32.dll", "user32.dll"}).is_game(99, 0.0))

    def test_windowed_game_keeps_the_controller_too(self):
        self.assertTrue(self.make(covers=False, modules={"xinput1_4.dll"}).is_game(99, 0.0))

    def test_exclusive_state_only_counts_for_a_window_covering_the_screen(self):
        self.assertFalse(self.make(covers=False, modules={"kernel32.dll"}, exclusive=True).is_game(99, 0.0))

    def test_windows_command_reports_the_detected_mode(self):
        engine = self.make(modules={"xinput1_4.dll"})
        sent = []
        engine.emit = sent.append
        with mock.patch.object(winman, "list_windows", return_value=[winman.Win(5, "Game", "game.exe", "p")]):
            engine.handle({"id": 1, "cmd": "windows"})
        self.assertEqual(sent[0]["data"][0]["game"], True)

    def test_exclusive_direct3d_full_screen_is_a_game(self):
        self.assertTrue(self.make(exclusive=True).is_game(99, 0.0))

    def test_protected_process_that_cannot_be_inspected_keeps_the_controller(self):
        self.assertTrue(self.make(modules=None).is_game(99, 0.0))

    def test_overrides_beat_detection(self):
        self.assertFalse(self.make(exe="Steam.exe", modules={"xinput1_4.dll"}, mouse_apps=["steam.exe"]).is_game(99, 0.0))
        self.assertTrue(self.make(exe="Odd.exe", covers=False, game_apps=["odd.exe"]).is_game(99, 0.0))

    def test_default_config_keeps_launchers_on_the_mouse(self):
        self.assertIn("steam.exe", apps.load_config()["mouse_apps"])

    def test_toggle_flips_between_game_and_mouse_and_remembers(self):
        engine = self.make(exe="Some.exe", modules={"xinput1_4.dll"})
        with mock.patch.object(apps, "save_config"):
            self.assertFalse(engine.toggle_game(99, 0.0))  # detected as a game, so it becomes a mouse app
            self.assertEqual((engine.cfg["mouse_apps"], engine.cfg["game_apps"]), (["Some.exe"], []))
            self.assertFalse(engine.is_game(99, 1.0))
            engine.toggle_game(99, 1.0)
            self.assertEqual((engine.cfg["mouse_apps"], engine.cfg["game_apps"]), ([], ["Some.exe"]))
            self.assertTrue(engine.is_game(99, 2.0))


class SteamGuardTests(IsolatedConfig):
    def run_guard(self, exe, launching=None, pushed=0):
        engine = Engine()
        engine.ui_hwnd = 1
        engine.pushed = pushed
        engine.launch = {"path": "x", "exe": launching} if launching else None
        calls = []
        with mock.patch.object(winman, "exe_name", return_value=exe), \
                mock.patch.object(winman, "minimize", lambda h: calls.append(("minimize", h))), \
                mock.patch.object(winman, "focus", lambda h: calls.append(("focus", h))):
            engine.reclaim_from_steam(99)
        return calls

    def test_steam_window_after_guide_is_minimized_and_ui_comes_back(self):
        self.assertEqual(self.run_guard("steam.exe"), [("minimize", 99), ("focus", 1)])
        self.assertEqual(self.run_guard("SteamWebHelper.exe"), [("minimize", 99), ("focus", 1)])

    def test_steam_is_left_alone_when_the_user_just_launched_steam(self):
        self.assertEqual(self.run_guard("steam.exe", launching="steam.exe"), [])

    def test_launching_another_app_does_not_switch_the_guard_off(self):
        self.assertEqual(self.run_guard("steam.exe", launching="EpicGamesLauncher.exe"),
                         [("minimize", 99), ("focus", 1)])

    def test_the_guard_gives_up_after_a_few_tries(self):
        self.assertEqual(self.run_guard("steam.exe", pushed=3), [])

    def test_only_the_launched_programs_windows_are_made_full_screen(self):
        engine = Engine()
        engine.cfg["launch_fullscreen"] = True
        engine.launch = {"path": "x", "exe": "EpicGamesLauncher.exe", "deadline": 10 ** 9, "seen": set(), "shown": False}
        windows = [winman.Win(1, "Epic", "epicgameslauncher.exe", "p"), winman.Win(2, "Steam", "steamwebhelper.exe", "p")]
        made = []
        with mock.patch.object(winman, "foreground", return_value=0), \
                mock.patch.object(winman, "list_windows", return_value=windows), \
                mock.patch.object(winman, "fullscreenize", lambda h: made.append(h)):
            engine.watch_launch(0.0)
        self.assertEqual(made, [1])

    def test_other_apps_are_left_alone(self):
        self.assertEqual(self.run_guard("game.exe"), [])


class AppsTests(IsolatedConfig):
    def test_scan_skips_helper_shortcuts_and_dedupes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            for root, names in ((a, ["Cool Game.lnk", "Uninstall Cool Game.lnk", "Readme.lnk"]),
                                (b, ["cool game.lnk", "Other App.lnk"])):
                for n in names:
                    (Path(root) / n).write_bytes(b"")
            found = [x.name for x in apps.scan([Path(a), Path(b)])]
        self.assertEqual(found, ["Cool Game", "Other App"])

    def test_scan_skips_system_tool_folders(self):
        with tempfile.TemporaryDirectory() as root:
            for rel in ("Administrative Tools/Services.lnk", "Windows Tools/Registry.lnk", "Games/Doom.lnk", "Notes.lnk"):
                path = Path(root) / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"")
            found = [(x.name, x.folder) for x in apps.scan([Path(root)])]
        self.assertEqual(found, [("Doom", "Games"), ("Notes", "")])

    def test_config_defaults_are_not_shared_between_loads(self):
        a, b = apps.load_config(), apps.load_config()
        a["game_apps"].append("x.exe")
        self.assertEqual(b["game_apps"], [])

    def test_recent_prefers_used_then_game_like_names(self):
        a, b, c = (apps.App(n, f"/{n}") for n in ("Notepad", "Steam", "Calc"))
        cfg = {"usage": {"/Calc": 10}}
        self.assertEqual([x.name for x in apps.recent([a, b, c], cfg, limit=2)], ["Calc", "Steam"])


if __name__ == "__main__":
    unittest.main()
