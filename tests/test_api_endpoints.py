import unittest
from fastapi.testclient import TestClient
from app import app
from database.db import get_db
from database.repositories import PresetRepository
from engine.mixer import get_mixer
from engine.script_runner import get_script_runner


class TestApiEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db = get_db()
        db.init_database()
        cls.client = TestClient(app)

    def test_grand_master_api(self):
        # GET default
        res = self.client.get("/api/master/grand_master")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("level", data)
        self.assertIn("percent", data)

        # POST level
        res = self.client.post("/api/master/grand_master", json={"level": 0.75})
        self.assertEqual(res.status_code, 200)
        self.assertAlmostEqual(res.json()["level"], 0.75)
        self.assertEqual(res.json()["percent"], 75)

        # POST percent
        res = self.client.post("/api/master/grand_master", json={"percent": 50})
        self.assertEqual(res.status_code, 200)
        self.assertAlmostEqual(res.json()["level"], 0.50)
        self.assertEqual(res.json()["percent"], 50)

        # Reset to 100%
        self.client.post("/api/master/grand_master", json={"percent": 100})

    def test_script_speed_api(self):
        # GET default
        res = self.client.get("/api/scripts/speed")
        self.assertEqual(res.status_code, 200)
        self.assertIn("multiplier", res.json())

        # POST speed
        res = self.client.post("/api/scripts/speed", json={"multiplier": 2.25})
        self.assertEqual(res.status_code, 200)
        self.assertAlmostEqual(res.json()["multiplier"], 2.25)

        # Verify getter matches
        res2 = self.client.get("/api/scripts/speed")
        self.assertAlmostEqual(res2.json()["multiplier"], 2.25)

        # Reset to 1.0
        self.client.post("/api/scripts/speed", json={"multiplier": 1.0})

    def test_preset_trigger_with_fade(self):
        repo = PresetRepository()
        preset_id = repo.create("Test Fade Look", {1: 180, 2: 90}, "Test preset", "test")

        # Instant cut trigger (fade_time 0)
        res_cut = self.client.post(f"/api/presets/{preset_id}/trigger", json={"fade_time": 0.0})
        self.assertEqual(res_cut.status_code, 200)
        self.assertTrue(res_cut.json()["success"])
        mixer = get_mixer()
        self.assertEqual(mixer.get_channel(1), 180)
        self.assertEqual(mixer.get_channel(2), 90)

        # Crossfade trigger (fade_time 0.1s)
        mixer.set_channels({1: 0, 2: 0})
        res_fade = self.client.post(f"/api/presets/{preset_id}/trigger", json={"fade_time": 0.1})
        self.assertEqual(res_fade.status_code, 200)
        self.assertTrue(res_fade.json()["success"])
        self.assertEqual(res_fade.json()["fade_time"], 0.1)


if __name__ == "__main__":
    unittest.main()
