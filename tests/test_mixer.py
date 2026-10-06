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


if __name__ == "__main__":
    unittest.main()
