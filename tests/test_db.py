import tempfile
import unittest
from pathlib import Path

from database.db import Database
from database.repositories import (
    FixtureRepository,
    PresetRepository,
    ShowScriptRepository,
    SettingsRepository,
    HealthLogRepository,
    WizardSessionRepository,
)


class TestDatabaseAndRepositories(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_dmx.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_database_initialization_and_integrity(self):
        check = self.db.check_integrity()
        self.assertTrue(check["ok"], f"Integrity check failed: {check}")

    def test_settings_repository(self):
        repo = SettingsRepository(self.db)
        repo.set("test_key", "test_val")
        self.assertEqual(repo.get("test_key"), "test_val")
        self.assertEqual(repo.get("missing_key", "default"), "default")
        
        repo.set("test_key", "updated_val")
        self.assertEqual(repo.get("test_key"), "updated_val")

        repo.delete("test_key")
        self.assertIsNone(repo.get("test_key"))

    def test_fixture_repository(self):
        repo = FixtureRepository(self.db)
        fix_id = repo.create(
            fixture_data={
                "name": "Test LED Par",
                "model": "Par 4CH",
                "manufacturer": "Acme",
                "start_channel": 10,
                "channel_count": 4,
                "group_tag": "backline",
            },
            channels=[
                {"channel_offset": 0, "channel_type": "dimmer", "label": "Dimmer", "default_value": 0},
                {"channel_offset": 1, "channel_type": "red", "label": "Red", "default_value": 0},
                {"channel_offset": 2, "channel_type": "green", "label": "Green", "default_value": 0},
                {"channel_offset": 3, "channel_type": "blue", "label": "Blue", "default_value": 0},
            ],
        )
        self.assertGreater(fix_id, 0)

        fixture = repo.get_by_id(fix_id)
        self.assertIsNotNone(fixture)
        self.assertEqual(fixture["name"], "Test LED Par")
        self.assertEqual(len(fixture["channels"]), 4)

        # Test Cascade Delete
        deleted = repo.delete(fix_id)
        self.assertTrue(deleted)
        self.assertIsNone(repo.get_by_id(fix_id))

    def test_preset_repository(self):
        repo = PresetRepository(self.db)
        preset_id = repo.create(
            name="Warm Sunset",
            channel_payload={"1": 255, "2": 128, "3": 0},
            description="Warm color",
            category="custom",
        )
        preset = repo.get_by_id(preset_id)
        self.assertIsNotNone(preset)
        self.assertEqual(preset["name"], "Warm Sunset")
        self.assertEqual(preset["channel_payload"], {"1": 255, "2": 128, "3": 0})

    def test_show_script_repository(self):
        repo = ShowScriptRepository(self.db)
        script_id = repo.create(
            name="Test Chase",
            footprint_channels=[1, 2, 3, 4],
            python_code="# test code\npass",
            description="Simple chase",
        )
        script = repo.get_by_id(script_id)
        self.assertIsNotNone(script)
        self.assertEqual(script["footprint_channels"], [1, 2, 3, 4])

    def test_health_log_repository(self):
        repo = HealthLogRepository(self.db)
        log_id = repo.log("hardware", "warning", "Device disconnected", {"port": "/dev/ttyUSB0"})
        self.assertGreater(log_id, 0)

        recent = repo.get_recent(limit=10)
        self.assertTrue(any(l["id"] == log_id for l in recent))

    def test_wizard_session_repository(self):
        repo = WizardSessionRepository(self.db)
        session_id = repo.create_session("Unknown Mover", 20, 16)
        session = repo.get_session(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session["fixture_name"], "Unknown Mover")
        self.assertEqual(session["transcript"], [])


if __name__ == "__main__":
    unittest.main()
