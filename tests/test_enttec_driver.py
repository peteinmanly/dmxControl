import unittest
from engine.hardware import VirtualDMXDriver, EnttecOpenDMXDriver, DMXHardwareDaemon
from engine.mixer import DMXMixer


class TestHardwareDrivers(unittest.TestCase):
    def test_virtual_driver_lifecycle(self):
        driver = VirtualDMXDriver()
        self.assertTrue(driver.open())
        self.assertFalse(driver.is_connected())  # No physical DMX hardware
        self.assertTrue(driver.is_active())

        frame = bytes([128] * 512)
        self.assertTrue(driver.send_frame(frame))

        diag = driver.get_diagnostics()
        self.assertEqual(diag["frames_sent"], 1)
        self.assertEqual(diag["status"], "simulation")

        driver.close()
        self.assertFalse(driver.is_active())

    def test_enttec_open_driver_graceful_missing_port(self):
        # When given a non-existent serial port, it should fail to open cleanly without throwing unhandled exceptions
        driver = EnttecOpenDMXDriver(port="/dev/nonexistent_serial_port_xyz")
        opened = driver.open()
        self.assertFalse(opened)
        self.assertFalse(driver.is_connected())
        diag = driver.get_diagnostics()
        self.assertIn("last_error", diag)

    def test_hardware_daemon_virtual_mode(self):
        mixer = DMXMixer()
        mixer.set_channel(1, 255)

        daemon = DMXHardwareDaemon(mixer=mixer, driver_type="virtual")
        daemon.set_fps(35)
        self.assertEqual(daemon.target_fps, 35)

        status = daemon.get_status()
        self.assertEqual(status["driver_mode"], "virtual")
        self.assertFalse(status["hardware_connected"])
        self.assertEqual(status["driver_diagnostics"]["status"], "simulation")


if __name__ == "__main__":
    unittest.main()
