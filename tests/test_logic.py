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


class SteamGuardTests(unittest.TestCase):
    def run_guard(self, exe, launching=False):
        engine = Engine()
        engine.ui_hwnd = 1
        engine.launch = {"path": "x"} if launching else None
        calls = []
        with mock.patch.object(winman, "exe_name", return_value=exe), \
                mock.patch.object(winman, "minimize", lambda h: calls.append(("minimize", h))), \
                mock.patch.object(winman, "focus", lambda h: calls.append(("focus", h))):
            engine.reclaim_from_steam(99)
        return calls

    def test_steam_window_after_guide_is_minimized_and_ui_comes_back(self):
        self.assertEqual(self.run_guard("steam.exe"), [("minimize", 99), ("focus", 1)])
        self.assertEqual(self.run_guard("SteamWebHelper.exe"), [("minimize", 99), ("focus", 1)])

    def test_steam_is_left_alone_when_the_user_just_launched_something(self):
        self.assertEqual(self.run_guard("steam.exe", launching=True), [])

    def test_other_apps_are_left_alone(self):
        self.assertEqual(self.run_guard("game.exe"), [])


class AppsTests(unittest.TestCase):
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
