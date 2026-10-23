import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from xbox_mode import apps, mouse, sendinput, system, winman
from xbox_mode.engine import Engine
from xbox_mode.xinput import Pad
from tests.test_logic import IsolatedConfig

WORK = (0, 0, 1920, 1040)
SECOND = (1920, 0, 3840, 1040)


class WindowGeometryTests(unittest.TestCase):
    def test_snap_takes_half_of_the_work_area(self):
        self.assertEqual(winman.snap_rect(WORK, "left"), (0, 0, 960, 1040))
        self.assertEqual(winman.snap_rect(WORK, "right"), (960, 0, 960, 1040))
        self.assertEqual(winman.snap_rect(SECOND, "right"), (2880, 0, 960, 1040))

    def test_an_odd_width_is_not_lost(self):
        left, right = winman.snap_rect((0, 0, 1001, 500), "left"), winman.snap_rect((0, 0, 1001, 500), "right")
        self.assertEqual(left[2] + right[2], 1001)

    def test_moving_to_another_monitor_keeps_the_relative_place(self):
        self.assertEqual(winman.relocate_rect((480, 260, 1440, 780), WORK, SECOND), (2400, 260, 960, 520))

    def test_a_window_bigger_than_the_target_is_shrunk_to_fit(self):
        small = (0, 0, 800, 600)
        self.assertEqual(winman.relocate_rect((0, 0, 1600, 900), WORK, small), (0, 0, 800, 600))

    def test_monitor_is_found_by_the_centre_of_the_window(self):
        mons = [{"rect": (0, 0, 1920, 1080)}, {"rect": (1920, 0, 3840, 1080)}]
        self.assertEqual(winman.monitor_index(mons, (1800, 100, 2300, 500)), 1)  # centre x 2050
        self.assertEqual(winman.monitor_index(mons, (100, 100, 500, 500)), 0)
        self.assertEqual(winman.monitor_index(mons, (9000, 0, 9100, 10)), 0)  # off every monitor: the first


class PlacesAndStoreTests(IsolatedConfig):
    def test_store_apps_are_read_from_get_startapps_json(self):
        text = ('[{"Name":"Calculator","AppID":"Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"},'
                '{"Name":"Notepad++","AppID":"C:\\\\Program Files\\\\Notepad++\\\\notepad++.exe"},'
                '{"Name":"Uninstall Thing","AppID":"Pkg_x!App"}]')
        found = apps.parse_start_apps(text)
        self.assertEqual([(a.name, a.path, a.folder) for a in found],
                         [("Calculator", "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App", "Microsoft Store")])

    def test_a_single_app_and_garbage_are_handled(self):
        self.assertEqual(len(apps.parse_start_apps('{"Name":"Photos","AppID":"Pkg_x!App"}')), 1)
        self.assertEqual(apps.parse_start_apps("not json"), [])
        self.assertEqual(apps.parse_start_apps(""), [])

    def test_store_apps_join_the_scan_without_duplicating_shortcuts(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "Photos.lnk").write_bytes(b"")
            found = apps.scan([Path(root)], extra=[apps.App("photos", "shell:AppsFolder\\x!App"), apps.App("Maps", "shell:AppsFolder\\y!App")])
        self.assertEqual([a.name for a in found], ["Maps", "Photos"])

    def test_known_folders_lists_only_the_ones_that_exist(self):
        with tempfile.TemporaryDirectory() as home:
            (Path(home) / "Documents").mkdir()
            (Path(home) / "Downloads").mkdir()
            self.assertEqual([f["name"] for f in apps.known_folders(home)], ["Documents", "Downloads"])

    def test_recent_files_are_newest_first_and_limited(self):
        import os
        with tempfile.TemporaryDirectory() as recent:
            for i, name in enumerate(["old.lnk", "mid.lnk", "new.lnk"]):
                p = Path(recent) / name
                p.write_bytes(b"")
                os.utime(p, (1000 + i, 1000 + i))
            (Path(recent) / "ignored.txt").write_bytes(b"")
            self.assertEqual([f["name"] for f in apps.recent_files(2, recent)], ["new", "mid"])

    def test_windows_own_recent_entries_are_left_out(self):
        with tempfile.TemporaryDirectory() as recent:
            for name in ("ms-gamingoverlay---.lnk", "notes.lnk"):
                (Path(recent) / name).write_bytes(b"")
            self.assertEqual([f["name"] for f in apps.recent_files(5, recent)], ["notes"])

    def test_missing_recent_folder_is_fine(self):
        self.assertEqual(apps.recent_files(5, "Z:/definitely/not/here"), [])

    def test_places_put_favourite_sites_first(self):
        cfg = {"favorites": [{"name": "Site", "url": "https://example.com"}]}
        with mock.patch.object(apps, "known_folders", return_value=[{"kind": "folder", "name": "F", "path": "p"}]), \
                mock.patch.object(apps, "recent_files", return_value=[]):
            self.assertEqual([p["kind"] for p in apps.places(cfg)], ["site", "folder"])

    def test_new_settings_have_defaults(self):
        cfg = apps.load_config()
        self.assertEqual((cfg["run_as_admin"], cfg["ui_sounds"], cfg["show_hints"]), (False, True, True))


class SystemActionTests(unittest.TestCase):
    def test_volume_keys(self):
        with mock.patch.object(system, "send_vk") as send:
            for action in ("volume_up", "volume_down", "mute"):
                self.assertTrue(system.run(action))
        self.assertEqual([c.args[0] for c in send.call_args_list], [0xAF, 0xAE, 0xAD])

    def test_brightness_script_clamps_and_uses_the_delta(self):
        script = system.brightness_script(-10)
        self.assertIn("+(-10)", script)
        self.assertIn("Math]::Max(0", script)
        self.assertIn("Math]::Min(100", script)

    def test_settings_pages_open_through_the_shell(self):
        with mock.patch.object(system.os, "startfile") as start:
            self.assertTrue(system.run("bluetooth"))
        start.assert_called_once_with("ms-settings:bluetooth")

    def test_screenshot_is_win_shift_s(self):
        with mock.patch.object(system, "send_combo") as combo:
            system.run("screenshot")
        combo.assert_called_once_with([0x5B, 0x10, 0x53])

    def test_power_actions_run_the_matching_command(self):
        with mock.patch.object(system.subprocess, "Popen") as popen:
            system.run("restart")
        self.assertEqual(popen.call_args.args[0], ["shutdown", "/r", "/t", "0"])

    def test_unknown_action_is_refused_and_power_ones_are_flagged_destructive(self):
        self.assertFalse(system.run("format_c"))
        self.assertEqual(system.DESTRUCTIVE, {"sleep", "restart", "shutdown"})


class KeyComboTests(unittest.TestCase):
    def test_keys_go_down_in_order_and_up_in_reverse(self):
        sent = []
        with mock.patch.object(sendinput, "_send", lambda vk=0, scan=0, flags=0: sent.append((vk, flags))):
            sendinput.send_combo([0x11, 0x43])
        self.assertEqual(sent, [(0x11, 0), (0x43, 0), (0x43, 2), (0x11, 2)])

    def test_win_and_arrow_keys_are_sent_as_extended(self):
        sent = []
        with mock.patch.object(sendinput, "_send", lambda vk=0, scan=0, flags=0: sent.append((vk, flags))):
            sendinput.send_combo([0x5B, 0x25])
        self.assertEqual(sent, [(0x5B, 1), (0x25, 1), (0x25, 3), (0x5B, 3)])


class FakePad:
    def __init__(self):
        self.connected, self.battery = True, None
        self.stick_nav = True
        self.held, self.pressed, self.released = set(), set(), set()
        self.nav, self.lx, self.ly, self.rx, self.ry, self.lt, self.rt = [], 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    def update(self, now):
        pass

    def events(self):
        return []


class EngineFeatureTests(IsolatedConfig):
    def setUp(self):
        super().setUp()
        self.engine = Engine()
        self.engine.pad = FakePad()
        self.engine.refresh_store = lambda: None
        self.sent = []
        self.engine.emit = self.sent.append
        patch = mock.patch.object(winman, "foreground", return_value=0)
        patch.start()
        self.addCleanup(patch.stop)
        self.tick(-1.0)  # the first tick announces the pad and its battery; start each test after that
        self.sent.clear()

    def tick(self, now, held=(), pressed=()):
        self.engine.pad.held, self.engine.pad.pressed = set(held), set(pressed)
        self.engine.tick(now, 0.01)

    def test_a_short_guide_press_opens_the_switcher_when_released(self):
        self.tick(0.0, held={"guide"}, pressed={"guide"})
        self.assertEqual(self.sent, [])
        self.tick(0.2)
        self.assertEqual(self.sent, [{"t": "guide"}])

    def test_holding_guide_opens_quick_settings_once_and_not_the_switcher(self):
        self.tick(0.0, held={"guide"}, pressed={"guide"})
        self.tick(0.7, held={"guide"})
        self.tick(1.5, held={"guide"})
        self.tick(1.6)
        self.assertEqual(self.sent, [{"t": "guide_long"}])

    def test_battery_changes_are_reported_once(self):
        self.engine.pad.battery = "low"
        self.tick(0.1)
        self.tick(0.2)
        self.assertEqual(self.sent, [{"t": "battery", "level": "low"}])

    def test_window_actions_reach_the_window_manager(self):
        calls = []
        with mock.patch.object(winman, "maximize", lambda h: calls.append(("max", h))), \
                mock.patch.object(winman, "minimize", lambda h: calls.append(("min", h))), \
                mock.patch.object(winman, "snap", lambda h, side: calls.append(("snap", h, side))), \
                mock.patch.object(winman, "move_to_next_monitor", lambda h: calls.append(("move", h)) or True):
            for action in ("maximize", "minimize", "snap_left", "snap_right", "next_monitor"):
                self.assertTrue(self.engine.window_action(7, action))
            self.assertFalse(self.engine.window_action(7, "explode"))
        self.assertEqual(calls, [("max", 7), ("min", 7), ("snap", 7, "left"), ("snap", 7, "right"), ("move", 7)])

    def test_chord_accepts_codes_and_characters(self):
        with mock.patch("xbox_mode.engine.send_combo") as combo, mock.patch("xbox_mode.engine.vk_for_char", return_value=0x43):
            self.engine.handle({"cmd": "chord", "keys": [0x11, "c"]})
        combo.assert_called_once_with([0x11, 0x43])

    def test_chord_with_an_unknown_character_does_nothing(self):
        with mock.patch("xbox_mode.engine.send_combo") as combo, mock.patch("xbox_mode.engine.vk_for_char", return_value=None):
            self.engine.handle({"cmd": "chord", "keys": [0x11, "§"]})
        combo.assert_not_called()

    def test_favourites_can_be_added_and_removed(self):
        self.engine.handle({"cmd": "favorite_add", "url": "https://a.example", "name": "A"})
        self.engine.handle({"cmd": "favorite_add", "url": "https://a.example", "name": "A again"})
        urls = [f["url"] for f in self.engine.cfg["favorites"]]
        self.assertEqual(urls.count("https://a.example"), 1)
        self.engine.handle({"cmd": "favorite_remove", "url": "https://a.example"})
        self.assertNotIn("https://a.example", [f["url"] for f in self.engine.cfg["favorites"]])


class PadBatteryTests(unittest.TestCase):
    def pad(self, battery_type, level):
        pad = Pad()
        pad.connected = True

        def fake(slot, dev, ref):
            ref._obj.BatteryType, ref._obj.BatteryLevel = battery_type, level
            return 0
        pad._get_battery = fake
        return pad

    def test_levels_are_named(self):
        for level, name in enumerate(("empty", "low", "medium", "full")):
            pad = self.pad(2, level)
            pad._read_battery(0.0)
            self.assertEqual(pad.battery, name)

    def test_a_wired_pad_has_no_battery(self):
        pad = self.pad(1, 3)
        pad._read_battery(0.0)
        self.assertIsNone(pad.battery)

    def test_it_is_only_read_every_so_often(self):
        pad = self.pad(2, 3)
        pad._read_battery(0.0)
        pad._get_battery = None
        pad._read_battery(5.0)
        self.assertEqual(pad.battery, "full")


class MouseFeatureTests(unittest.TestCase):
    def pad(self, **kw):
        base = dict(lx=0.0, ly=0.0, rx=0.0, ry=0.0, lt=0.0, rt=0.0, pressed=set(), released=set(), nav=[])
        return SimpleNamespace(**{**base, **kw})

    def test_lb_copies_then_opens_the_clipboard_history(self):
        chords = []
        m = mouse.MouseMode()
        m._chord = lambda mod, key: chords.append((mod, key))
        timer = mock.Mock()
        with mock.patch.object(mouse, "user32"), mock.patch.object(mouse.threading, "Timer", return_value=timer) as made:
            m.apply(self.pad(pressed={"lb"}), 0.01)
        self.assertEqual(chords, [(0x11, 0x43)])                 # Ctrl+C right away
        self.assertEqual(made.call_args.args[1:], (m._chord, (0x5B, 0x56)))  # then Win+V after a short settle
        timer.start.assert_called_once()

    def test_right_stick_sideways_scrolls_horizontally(self):
        with mock.patch.object(mouse, "user32") as user32:
            m = mouse.MouseMode()
            for _ in range(20):
                m.apply(self.pad(rx=1.0), 0.01)
        wheel = [c.args for c in user32.mouse_event.call_args_list if c.args[0] == mouse.HWHEEL]
        self.assertTrue(wheel and all(a[3] > 0 for a in wheel))

    def test_clicking_the_right_stick_jumps_to_the_other_monitor(self):
        with mock.patch.object(mouse, "user32"), mock.patch.object(mouse.winman, "move_cursor_to_next_monitor") as jump:
            mouse.MouseMode().apply(self.pad(pressed={"rs"}), 0.01)
        jump.assert_called_once()


if __name__ == "__main__":
    unittest.main()
