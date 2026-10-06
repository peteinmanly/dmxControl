import unittest
from ai.show_generator import validate_script_ast


class TestASTSafetyValidator(unittest.TestCase):
    def test_safe_script_passes(self):
        safe_code = """
import math
import time

step = 0.0
while not stop_event.is_set():
    val = int((math.sin(step) + 1.0) * 127.5)
    dmx.set(1, val)
    step += 0.05
    time.sleep(0.025)
"""
        is_safe, err = validate_script_ast(safe_code)
        self.assertTrue(is_safe, f"Safe script rejected: {err}")
        self.assertIsNone(err)

    def test_prohibited_import_fails(self):
        unsafe_code = """
import os
import time

while not stop_event.is_set():
    time.sleep(0.1)
"""
        is_safe, err = validate_script_ast(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Unauthorized import 'os'", err)

    def test_prohibited_call_fails(self):
        unsafe_code = """
import time

while not stop_event.is_set():
    open("/tmp/secret.txt", "w")
    time.sleep(0.1)
"""
        is_safe, err = validate_script_ast(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("open", err)

    def test_eval_exec_fails(self):
        unsafe_code = """
import time

while not stop_event.is_set():
    eval("1 + 1")
    time.sleep(0.1)
"""
        is_safe, err = validate_script_ast(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("eval", err)

    def test_infinite_loop_without_stop_event_fails(self):
        unsafe_code = """
import time

while True:
    time.sleep(0.05)
"""
        is_safe, err = validate_script_ast(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("Infinite Loop Warning", err)

    def test_loop_without_sleep_fails(self):
        unsafe_code = """
while not stop_event.is_set():
    dmx.set(1, 255)
"""
        is_safe, err = validate_script_ast(unsafe_code)
        self.assertFalse(is_safe)
        self.assertIn("CPU Starvation Warning", err)


if __name__ == "__main__":
    unittest.main()
