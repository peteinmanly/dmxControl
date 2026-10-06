import time
import unittest
from engine.mixer import DMXMixer
from engine.script_runner import ScriptRunner


class TestScriptRunner(unittest.TestCase):
    def setUp(self):
        self.mixer = DMXMixer()
        self.runner = ScriptRunner(mixer=self.mixer)

    def tearDown(self):
        self.runner.kill_all()

    def test_run_single_script(self):
        code = """
import time
while not stop_event.is_set():
    dmx.set(1, 200)
    time.sleep(0.01)
"""
        res = self.runner.start_script(
            script_id=1,
            name="Test Script 1",
            footprint=[1, 2],
            python_code=code,
        )
        self.assertTrue(res["success"])
        self.assertTrue(self.runner.is_running(1))

        # Wait briefly for thread execution
        time.sleep(0.05)
        self.assertEqual(self.mixer.get_channel(1), 200)
        self.assertEqual(self.mixer.get_channel_ownership()[0], "Script:1")

        # Stop script
        stopped = self.runner.stop_script(1)
        self.assertTrue(stopped)
        self.assertFalse(self.runner.is_running(1))
        self.assertIsNone(self.mixer.get_channel_ownership()[0])

    def test_collision_arbitration_halts_overlapping_script(self):
        code1 = """
import time
while not stop_event.is_set():
    dmx.set(1, 100)
    time.sleep(0.01)
"""
        code2 = """
import time
while not stop_event.is_set():
    dmx.set(1, 255)
    time.sleep(0.01)
"""
        # Start Script 1 on Channels 1..4
        self.runner.start_script(1, "Script 1", [1, 2, 3, 4], code1)
        self.assertTrue(self.runner.is_running(1))

        time.sleep(0.03)

        # Start Script 2 on Channels 3..6 (Overlaps Channel 3 & 4)
        res2 = self.runner.start_script(2, "Script 2", [3, 4, 5, 6], code2)
        self.assertTrue(res2["success"])

        # Script 1 should have been halted due to collision
        self.assertFalse(self.runner.is_running(1))
        self.assertTrue(self.runner.is_running(2))
        self.assertEqual(len(res2["halted_collisions"]), 1)
        self.assertEqual(res2["halted_collisions"][0]["id"], 1)

    def test_non_overlapping_scripts_run_concurrently(self):
        code_a = """
import time
while not stop_event.is_set():
    dmx.set(1, 100)
    time.sleep(0.01)
"""
        code_b = """
import time
while not stop_event.is_set():
    dmx.set(10, 200)
    time.sleep(0.01)
"""
        # Script A on 1..4, Script B on 10..14 (Disjoint)
        self.runner.start_script(101, "Script A", [1, 2, 3, 4], code_a)
        self.runner.start_script(102, "Script B", [10, 11, 12, 13, 14], code_b)

        time.sleep(0.03)

        self.assertTrue(self.runner.is_running(101))
        self.assertTrue(self.runner.is_running(102))

        self.assertEqual(self.mixer.get_channel(1), 100)
        self.assertEqual(self.mixer.get_channel(10), 200)

        # Kill all
        killed = self.runner.kill_all()
        self.assertEqual(killed, 2)
        self.assertFalse(self.runner.is_running(101))
        self.assertFalse(self.runner.is_running(102))


if __name__ == "__main__":
    unittest.main()
