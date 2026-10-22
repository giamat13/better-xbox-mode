import json
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from xbox_mode.config import load_config
from xbox_mode.heartbeat import HeartbeatServer, HeartbeatStore
from xbox_mode.policy import HANDLING, NATIVE


class FakeClock:
    def __init__(self, value=100.0):
        self.value = value

    def __call__(self):
        return self.value


class HeartbeatStoreTests(unittest.TestCase):
    def test_latest_reports_state_and_timestamp(self):
        clock = FakeClock(5.0)
        store = HeartbeatStore(clock=clock)
        self.assertIsNone(store.latest())
        store.record(HANDLING)
        self.assertEqual(store.latest().state, HANDLING)
        self.assertEqual(store.latest().received_at, 5.0)


class HeartbeatServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = HeartbeatStore()
        cls.server = HeartbeatServer(0, cls.store)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{cls.server.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def post(self, path, body, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(
            self.base + path, data=body if isinstance(body, bytes) else json.dumps(body).encode(),
            headers=headers, method="POST",
        )
        return urllib.request.urlopen(request, timeout=2)

    def test_valid_handling_heartbeat_is_recorded(self):
        response = self.post("/heartbeat", {"state": HANDLING})
        self.assertEqual(response.status, 204)
        self.assertEqual(self.store.latest().state, HANDLING)

    def test_native_state_is_recorded(self):
        self.post("/heartbeat", {"state": NATIVE})
        self.assertEqual(self.store.latest().state, NATIVE)

    def test_unknown_state_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/heartbeat", {"state": "bogus"})
        self.assertEqual(caught.exception.code, 400)

    def test_invalid_json_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/heartbeat", b"{not json")
        self.assertEqual(caught.exception.code, 400)

    def test_unknown_path_is_404(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/other", {"state": HANDLING})
        self.assertEqual(caught.exception.code, 404)

    def test_oversized_body_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post("/heartbeat", b"x" * 5000)
        self.assertEqual(caught.exception.code, 413)

    def test_status_endpoint_reports_latest_state(self):
        self.store.record(NATIVE)
        with urllib.request.urlopen(self.base + "/status", timeout=2) as response:
            body = json.loads(response.read())
        self.assertEqual(body["state"], NATIVE)
        self.assertGreaterEqual(body["age_seconds"], 0)

    def test_preflight_allows_only_extension_origins(self):
        request = urllib.request.Request(self.base + "/heartbeat", method="OPTIONS",
                                         headers={"Origin": "chrome-extension://abcdef"})
        response = urllib.request.urlopen(request, timeout=2)
        self.assertEqual(response.status, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "chrome-extension://abcdef")

        request = urllib.request.Request(self.base + "/heartbeat", method="OPTIONS",
                                         headers={"Origin": "https://evil.example"})
        response = urllib.request.urlopen(request, timeout=2)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))


class ConfigTests(unittest.TestCase):
    def test_missing_file_gives_defaults(self):
        config = load_config(None)
        self.assertEqual(config["heartbeat_port"], 8765)
        self.assertEqual(config["joystick_buttons"]["A"], 0)

    def test_file_values_merge_into_nested_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "config.json")
            path.write_text(json.dumps({"deadzone": 0.2, "joystick_buttons": {"A": 3}}))
            config = load_config(path)
            self.assertEqual(config["deadzone"], 0.2)
            self.assertEqual(config["joystick_buttons"]["A"], 3)
            self.assertEqual(config["joystick_buttons"]["B"], 1)

    def test_unknown_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "config.json")
            path.write_text(json.dumps({"dead_zone": 0.2}))
            with self.assertRaisesRegex(ValueError, "unknown config keys"):
                load_config(path)

    def test_out_of_range_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "config.json")
            path.write_text(json.dumps({"deadzone": 0.95}))
            with self.assertRaisesRegex(ValueError, "deadzone"):
                load_config(path)

    def test_bad_override_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "config.json")
            path.write_text(json.dumps({"overrides": {"game.exe": "maybe"}}))
            with self.assertRaisesRegex(ValueError, "overrides"):
                load_config(path)

    def test_example_config_loads_cleanly(self):
        example = Path(__file__).resolve().parent.parent / "config.example.json"
        config = load_config(example)
        self.assertEqual(config["tick_rate"], 120)


if __name__ == "__main__":
    unittest.main()
