import subprocess
import sys
import unittest


class IoTests(unittest.TestCase):
    def test_hebrew_survives_piped_stdio(self):
        code = "from xbox_mode import engine; engine.setup_io(); import sys; sys.stdout.write(sys.stdin.readline())"
        out = subprocess.run([sys.executable, "-c", code], input="שלום עולם\n".encode("utf-8"),
                             capture_output=True, check=True).stdout
        self.assertEqual(out.decode("utf-8").strip(), "שלום עולם")


if __name__ == "__main__":
    unittest.main()
