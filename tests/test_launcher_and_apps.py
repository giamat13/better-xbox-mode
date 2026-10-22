import tempfile
import unittest
from pathlib import Path

from xbox_mode.launcher import Launcher
from xbox_mode.launcher_apps import App, discover_apps, discover_linux, discover_windows, parse_desktop_entry


class LauncherTests(unittest.TestCase):
    def apps(self, count):
        return [App(f"app{i}") for i in range(count)]

    def test_moves_across_grid_and_clamps_at_edges(self):
        launcher = Launcher(self.apps(5), columns=2)
        launcher.move(1, 0)
        self.assertEqual(launcher.select().name, "app1")
        launcher.toggle()
        launcher.move(0, 1)
        self.assertEqual(launcher.select().name, "app3")
        launcher.toggle()
        launcher.move(0, 5)
        launcher.move(1, 0)
        self.assertEqual(launcher.select().name, "app4")

    def test_last_row_clamps_to_existing_apps(self):
        launcher = Launcher(self.apps(3), columns=2)
        launcher.move(0, 1)
        launcher.move(1, 0)
        self.assertEqual(launcher.select().name, "app2")

    def test_select_closes_and_returns_app(self):
        launcher = Launcher(self.apps(2))
        launcher.toggle()
        self.assertEqual(launcher.select().name, "app0")
        self.assertFalse(launcher.open)

    def test_empty_launcher_is_safe(self):
        launcher = Launcher([])
        launcher.move(1, 1)
        self.assertIsNone(launcher.select())
        self.assertEqual(launcher.tiles(), ())

    def test_only_one_tile_is_selected(self):
        launcher = Launcher(self.apps(3), columns=2)
        launcher.move(1, 0)
        selected = [tile.name for tile in launcher.tiles() if tile.selected]
        self.assertEqual(selected, ["app1"])


class DesktopEntryTests(unittest.TestCase):
    def test_reads_name_and_command(self):
        entry = parse_desktop_entry("[Desktop Entry]\nType=Application\nName=Files\nExec=nautilus --new-window\n")
        self.assertEqual(entry, {"name": "Files", "command": ["nautilus", "--new-window"]})

    def test_skips_hidden_and_no_display(self):
        base = "[Desktop Entry]\nType=Application\nName=X\nExec=x\n"
        self.assertIsNone(parse_desktop_entry(base + "Hidden=true\n"))
        self.assertIsNone(parse_desktop_entry(base + "NoDisplay=true\n"))

    def test_strips_field_codes_but_keeps_literal_percent(self):
        entry = parse_desktop_entry("[Desktop Entry]\nType=Application\nName=X\nExec=tool %U 100%% %f\n")
        self.assertEqual(entry["command"], ["tool", "100%"])

    def test_ignores_keys_outside_desktop_entry_section(self):
        text = "[Desktop Action New]\nName=Wrong\nExec=wrong\n[Desktop Entry]\nType=Application\nName=Right\nExec=right\n"
        self.assertEqual(parse_desktop_entry(text)["name"], "Right")

    def test_non_application_types_are_skipped(self):
        self.assertIsNone(parse_desktop_entry("[Desktop Entry]\nType=Link\nName=X\nURL=https://x\n"))

    def test_malformed_exec_is_skipped(self):
        self.assertIsNone(parse_desktop_entry("[Desktop Entry]\nType=Application\nName=X\nExec=foo 'bar\n"))


class DiscoveryTests(unittest.TestCase):
    def test_discover_linux_reads_fixture_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.desktop").write_text("[Desktop Entry]\nType=Application\nName=Beta\nExec=beta\n")
            (root / "b.desktop").write_text("[Desktop Entry]\nType=Application\nName=alpha\nExec=alpha\n")
            (root / "c.desktop").write_text("[Desktop Entry]\nType=Application\nName=Hidden\nExec=h\nHidden=true\n")
            apps = discover_linux([root, root / "missing"])
            self.assertEqual([a.name for a in apps], ["alpha", "Beta"])
            self.assertEqual(apps[0].command, ("alpha",))

    def test_discover_windows_collects_shortcuts_and_skips_uninstallers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Games").mkdir()
            (root / "Games" / "Chess.lnk").write_bytes(b"")
            (root / "Browser.url").write_bytes(b"")
            (root / "Uninstall Chess.lnk").write_bytes(b"")
            (root / "readme.txt").write_text("not an app")
            apps = discover_windows([root])
            self.assertEqual([a.name for a in apps], ["Browser", "Chess"])
            self.assertTrue(all(a.path and a.command is None for a in apps))

    def test_duplicate_names_are_listed_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "one").mkdir()
            (root / "two").mkdir()
            (root / "one" / "Editor.lnk").write_bytes(b"")
            (root / "two" / "editor.lnk").write_bytes(b"")
            self.assertEqual(len(discover_windows([root])), 1)

    def test_extra_apps_override_discovered_entries(self):
        apps = discover_apps(
            [{"name": "Calc", "command": "calc --mode basic"}, {"name": "Notes", "path": "C:/notes.url"}],
            windows=False,
        )
        by_name = {a.name: a for a in apps}
        self.assertEqual(by_name["Calc"].command, ("calc", "--mode", "basic"))
        self.assertEqual(by_name["Notes"].path, "C:/notes.url")


if __name__ == "__main__":
    unittest.main()
