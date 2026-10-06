import unittest
from ai.self_healing import AIDoctor


class TestAIDoctorSelfHealing(unittest.TestCase):
    def setUp(self):
        self.doctor = AIDoctor()

    def test_collect_telemetry(self):
        telemetry = self.doctor.collect_telemetry()
        self.assertIn("os", telemetry)
        self.assertIn("user_permissions", telemetry)
        self.assertIn("serial_devices", telemetry)
        self.assertIn("database_integrity", telemetry)
        self.assertIn("hardware_daemon", telemetry)

    def test_diagnose_and_heal_returns_status(self):
        result = self.doctor.diagnose_and_heal()
        self.assertIn("status", result)
        self.assertIn(result["status"], ["HEALTHY", "DEGRADED", "CRITICAL", "DISCONNECTED"])
        self.assertIn("telemetry", result)
        self.assertIsInstance(result["issues"], list)
        self.assertIsInstance(result["auto_actions_taken"], list)


if __name__ == "__main__":
    unittest.main()
