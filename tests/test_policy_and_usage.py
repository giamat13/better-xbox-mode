import unittest

from xbox_mode.gamepad_usage import GamepadUsageCache, uses_gamepad_api
from xbox_mode.policy import HANDLING, NATIVE, RELEASED, EmulationPolicy, PageReport


class UsesGamepadApiTests(unittest.TestCase):
    def test_xinput_is_detected_regardless_of_case(self):
        self.assertTrue(uses_gamepad_api(["KERNEL32.dll", "XInput1_4.DLL"]))

    def test_every_xinput_version_is_detected(self):
        for name in ("xinput1_1.dll", "xinput1_2.dll", "xinput1_3.dll", "xinput9_1_0.dll", "xinputuap.dll"):
            self.assertTrue(uses_gamepad_api([name]), name)

    def test_windows_gaming_input_is_detected(self):
        self.assertTrue(uses_gamepad_api(["Windows.Gaming.Input.dll"]))

    def test_dinput_is_ignored_unless_enabled(self):
        self.assertFalse(uses_gamepad_api(["dinput8.dll"]))
        self.assertTrue(uses_gamepad_api(["dinput8.dll"], include_dinput=True))

    def test_unrelated_modules_are_not_detected(self):
        self.assertFalse(uses_gamepad_api(["user32.dll", "d3d11.dll", "hid.dll"]))


class GamepadUsageCacheTests(unittest.TestCase):
    def test_result_is_cached_within_refresh_window(self):
        calls = []

        def list_modules(pid):
            calls.append(pid)
            return ["xinput1_4.dll"]

        cache = GamepadUsageCache(list_modules, refresh_seconds=2.0)
        self.assertTrue(cache.check(10, now=0.0))
        self.assertTrue(cache.check(10, now=1.5))
        self.assertEqual(calls, [10])
        cache.check(10, now=2.5)
        self.assertEqual(calls, [10, 10])

    def test_no_process_means_no_gamepad(self):
        cache = GamepadUsageCache(lambda pid: ["xinput1_4.dll"])
        self.assertFalse(cache.check(None, now=0.0))


class EmulationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = EmulationPolicy({"Notepad.EXE": "emulate", "steam.exe": "pass_through"}, stale_after=1.0)

    def test_plain_app_is_emulated(self):
        self.assertTrue(self.policy.decide("writer.exe", False, None, now=0.0))

    def test_app_with_pad_api_is_passed_through(self):
        self.assertFalse(self.policy.decide("game.exe", True, None, now=0.0))

    def test_override_beats_detection_in_both_directions(self):
        self.assertTrue(self.policy.decide("notepad.exe", True, None, now=0.0))
        self.assertFalse(self.policy.decide("steam.exe", False, None, now=0.0))

    def test_chrome_with_fresh_handling_report_is_left_to_extension(self):
        report = PageReport(HANDLING, received_at=10.0)
        self.assertFalse(self.policy.decide("chrome.exe", False, report, now=10.5))

    def test_chrome_on_native_page_is_passed_through(self):
        report = PageReport(NATIVE, received_at=10.0)
        self.assertFalse(self.policy.decide("chrome.exe", False, report, now=10.5))

    def test_stale_chrome_report_falls_back_to_emulation(self):
        report = PageReport(HANDLING, received_at=10.0)
        self.assertTrue(self.policy.decide("chrome.exe", False, report, now=11.5))

    def test_missing_chrome_report_falls_back_to_emulation(self):
        self.assertTrue(self.policy.decide("msedge.exe", False, None, now=0.0))

    def test_chrome_handed_back_to_desktop_is_emulated(self):
        report = PageReport(RELEASED, received_at=10.0)
        self.assertTrue(self.policy.decide("chrome.exe", False, report, now=10.5))

    def test_exe_name_is_case_insensitive(self):
        self.assertFalse(self.policy.decide("Chrome.EXE", False, PageReport(NATIVE, 0.0), now=0.1))


if __name__ == "__main__":
    unittest.main()
