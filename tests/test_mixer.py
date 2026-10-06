import unittest
from engine.mixer import DMXMixer


class TestDMXMixer(unittest.TestCase):
    def setUp(self):
        self.mixer = DMXMixer(universe_size=512)

    def test_buffer_initialization(self):
        frame = self.mixer.get_frame()
        self.assertEqual(len(frame), 512)
        self.assertTrue(all(b == 0 for b in frame))

    def test_single_channel_update(self):
        ok = self.mixer.set_channel(1, 255, owner="Preset:1")
        self.assertTrue(ok)
        self.assertEqual(self.mixer.get_channel(1), 255)

        # Clamping
        self.mixer.set_channel(1, 300)
        self.assertEqual(self.mixer.get_channel(1), 255)
        self.mixer.set_channel(1, -50)
        self.assertEqual(self.mixer.get_channel(1), 0)

        # Out of bounds
        self.assertFalse(self.mixer.set_channel(0, 100))
        self.assertFalse(self.mixer.set_channel(513, 100))

    def test_bulk_channel_update(self):
        count = self.mixer.set_channels({1: 100, 2: 200, 3: 50}, owner="Script:1")
        self.assertEqual(count, 3)
        self.assertEqual(self.mixer.get_channel(1), 100)
        self.assertEqual(self.mixer.get_channel(2), 200)
        self.assertEqual(self.mixer.get_channel(3), 50)

    def test_ownership_tracking_and_release(self):
        self.mixer.set_channel(10, 255, owner="Script:42")
        ownership = self.mixer.get_channel_ownership()
        self.assertEqual(ownership[9], "Script:42")

        # Release matching owner
        self.mixer.release_channels([10], owner="Script:42")
        ownership_after = self.mixer.get_channel_ownership()
        self.assertIsNone(ownership_after[9])

    def test_master_blackout(self):
        self.mixer.set_channels({1: 255, 10: 128, 512: 200}, owner="Preset:1")
        self.mixer.blackout()
        frame = self.mixer.get_frame()
        self.assertTrue(all(b == 0 for b in frame))
        ownership = self.mixer.get_channel_ownership()
        self.assertTrue(all(o is None for o in ownership))

    def test_grand_master_scaling(self):
        self.mixer.set_channels({1: 200, 2: 100, 3: 50})
        self.assertEqual(self.mixer.get_channel(1, scaled=False), 200)

        # Scale to 50%
        applied = self.mixer.set_grand_master(0.5)
        self.assertEqual(applied, 0.5)
        self.assertEqual(self.mixer.get_grand_master(), 0.5)

        # Scaled get_channel
        self.assertEqual(self.mixer.get_channel(1, scaled=True), 100)
        self.assertEqual(self.mixer.get_channel(2, scaled=True), 50)
        self.assertEqual(self.mixer.get_channel(3, scaled=True), 25)

        # Frame should reflect 50% scaling
        frame = self.mixer.get_frame()
        self.assertEqual(frame[0], 100)
        self.assertEqual(frame[1], 50)
        self.assertEqual(frame[2], 25)

        # Universe state should reflect grand_master
        state = self.mixer.get_universe_state()
        self.assertEqual(state["grand_master"], 0.5)
        self.assertEqual(state["channels"][0], 100)

        # Scale to 0%
        self.mixer.set_grand_master(0.0)
        frame_zero = self.mixer.get_frame()
        self.assertTrue(all(b == 0 for b in frame_zero))
        # Base buffer unchanged
        self.assertEqual(self.mixer.get_channel(1, scaled=False), 200)

        # Restore to 100%
        self.mixer.set_grand_master(1.0)
        self.assertEqual(self.mixer.get_channel(1, scaled=True), 200)

    def test_smooth_crossfade(self):
        import time
        self.mixer.set_channels({1: 0, 2: 100})
        self.mixer.fade_to_channels({1: 200, 2: 0}, duration_sec=0.1, owner="Preset:5")

        ownership = self.mixer.get_channel_ownership()
        self.assertEqual(ownership[0], "Preset:5")
        self.assertEqual(ownership[1], "Preset:5")

        time.sleep(0.18)
        self.assertEqual(self.mixer.get_channel(1), 200)
        self.assertEqual(self.mixer.get_channel(2), 0)

    def test_blackout_cancels_active_crossfade(self):
        import time
        self.mixer.fade_to_channels({1: 255}, duration_sec=1.0)
        time.sleep(0.04)
        self.mixer.blackout()
        time.sleep(0.08)
        self.assertEqual(self.mixer.get_channel(1), 0)


if __name__ == "__main__":
    unittest.main()
