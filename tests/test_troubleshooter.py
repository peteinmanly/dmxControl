import unittest
from ai.terminal_troubleshooter import TerminalTroubleshooter, QUICK_RECIPES


class TestTerminalTroubleshooter(unittest.TestCase):
    def setUp(self):
        self.troubleshooter = TerminalTroubleshooter()

    def test_quick_recipe_retrieval(self):
        recipes = self.troubleshooter.get_quick_recipes()
        self.assertIn("audit_usb", recipes)
        self.assertIn("check_permissions", recipes)
        self.assertIn("check_conflicts", recipes)
        self.assertIn("check_latency_and_logs", recipes)

    def test_generate_command_from_recipe(self):
        res = self.troubleshooter.generate_command("", recipe_key="audit_usb")
        self.assertEqual(res["command"], QUICK_RECIPES["audit_usb"]["command"])
        self.assertIn("Inspects USB", res["explanation"])

    def test_analyze_terminal_output_detects_brltty(self):
        fake_output = """
● brltty.service - Braille Device Driver
     Loaded: loaded (/lib/systemd/system/brltty.service)
     Active: active (running) since Wed 2026-10-07 08:00:00
"""
        analysis = self.troubleshooter.analyze_output(
            issue_description="Cannot connect to Enttec box",
            command_run="systemctl status brltty",
            terminal_output=fake_output,
        )
        self.assertIn("brltty", analysis["diagnosis"].lower())
        self.assertTrue(any("mask brltty" in c["command"] for c in analysis["remediation_commands"]))

    def test_analyze_terminal_output_detects_dialout(self):
        fake_output = "uid=1000(user) gid=1000(user) groups=1000(user),27(sudo)"
        analysis = self.troubleshooter.analyze_output(
            issue_description="Permission denied on /dev/ttyUSB0",
            command_run="groups",
            terminal_output=fake_output,
        )
        self.assertIn("permission", analysis["diagnosis"].lower())
        self.assertTrue(any("dialout" in c["command"] for c in analysis["remediation_commands"]))


if __name__ == "__main__":
    unittest.main()
