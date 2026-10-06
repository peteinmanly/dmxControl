"""
DMX512 Hardware Drivers and Background Output Loop Daemon.
Defaults to Enttec Open DMX USB on Linux Mint with automatic Virtual fallback.
"""

import glob
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

import config
from .mixer import DMXMixer, get_mixer

try:
    import serial
except ImportError:
    serial = None

_daemon_lock = threading.Lock()
_global_daemon_instance: Optional["DMXHardwareDaemon"] = None


class BaseDMXDriver(ABC):
    @abstractmethod
    def open(self) -> bool:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def send_frame(self, frame: bytes) -> bool:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    def get_diagnostics(self) -> Dict[str, Any]:
        pass


class VirtualDMXDriver(BaseDMXDriver):
    """Software-only dummy driver for development, unit testing, and offline busking."""

    def __init__(self):
        self._connected = False
        self._frames_sent = 0
        self._last_send_time = 0.0

    def open(self) -> bool:
        self._connected = True
        return True

    def close(self) -> None:
        self._connected = False

    def send_frame(self, frame: bytes) -> bool:
        if not self._connected:
            return False
        self._frames_sent += 1
        self._last_send_time = time.time()
        return True

    def is_connected(self) -> bool:
        return self._connected

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "driver_name": "Virtual / Dummy DMX",
            "connected": self._connected,
            "port": "Virtual (In-Memory)",
            "frames_sent": self._frames_sent,
            "last_send_timestamp": self._last_send_time,
            "status": "active" if self._connected else "stopped",
            "hardware_notes": "Simulation mode. No physical lights connected.",
        }


class EnttecOpenDMXDriver(BaseDMXDriver):
    """
    Enttec Open DMX USB Driver (FTDI FT232R UART).
    Generates exact DMX512 timing:
      - Break >= 88us (100us standard)
      - Mark After Break (MAB) >= 8us (12us standard)
      - 250k baud, 8N2, Start Code 0x00 + 512 universe bytes.
    """

    def __init__(self, port: Optional[str] = None):
        self.requested_port = port or config.DEFAULT_SERIAL_PORT
        self.actual_port: Optional[str] = None
        self._ser: Optional[Any] = None
        self._frames_sent = 0
        self._last_error: Optional[str] = None
        self._latency_timer_val: Optional[int] = None

    def auto_discover_port(self) -> Optional[str]:
        """Scans Linux Mint serial devices by-id and by-path for Enttec/FTDI devices."""
        # 1. Check /dev/serial/by-id/
        by_id_devices = glob.glob("/dev/serial/by-id/*")
        for dev in by_id_devices:
            dev_lower = dev.lower()
            if "enttec" in dev_lower or "ftdi" in dev_lower:
                return dev

        # 2. Check udev symlink if present
        if os.path.exists("/dev/enttec_open_dmx"):
            return "/dev/enttec_open_dmx"

        # 3. Check requested or standard /dev/ttyUSB*
        if os.path.exists(self.requested_port):
            return self.requested_port

        tty_usb_devs = sorted(glob.glob("/dev/ttyUSB*"))
        if tty_usb_devs:
            return tty_usb_devs[0]

        return None

    def check_linux_latency_timer(self, port_path: str) -> Optional[int]:
        """Checks Linux FTDI sysfs latency timer (ideal: 1ms for low-jitter DMX)."""
        port_name = os.path.basename(port_path)
        sysfs_path = f"/sys/bus/usb-serial/devices/{port_name}/latency_timer"
        if os.path.exists(sysfs_path):
            try:
                with open(sysfs_path, "r") as f:
                    val = int(f.read().strip())
                    self._latency_timer_val = val
                    return val
            except Exception:
                pass
        return None

    def open(self) -> bool:
        if serial is None:
            self._last_error = "pyserial package is not installed."
            return False

        discovered = self.auto_discover_port()
        if not discovered:
            self._last_error = f"No Enttec / FTDI serial device detected (tried {self.requested_port})."
            return False

        self.actual_port = discovered
        try:
            self._ser = serial.Serial(
                port=self.actual_port,
                baudrate=config.SERIAL_BAUDRATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO,
                timeout=0.1,
                write_timeout=0.1,
            )
            # Check latency timer
            self.check_linux_latency_timer(self.actual_port)
            self._last_error = None
            return True
        except serial.SerialException as se:
            err_msg = str(se)
            if "Permission denied" in err_msg:
                self._last_error = f"Permission denied on {self.actual_port}. User must belong to 'dialout' group."
            elif "Device or resource busy" in err_msg:
                self._last_error = f"Device {self.actual_port} is busy. A daemon like 'brltty' or another app has locked it."
            else:
                self._last_error = f"Serial error: {err_msg}"
            self._ser = None
            return False
        except Exception as e:
            self._last_error = f"Failed to open {self.actual_port}: {str(e)}"
            self._ser = None
            return False

    def close(self) -> None:
        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception:
                pass
        self._ser = None

    def send_frame(self, frame: bytes) -> bool:
        if not self._ser or not self._ser.is_open:
            return False

        try:
            # 1. Generate DMX Break (minimum 88us)
            self._ser.break_condition = True
            time.sleep(config.DMX_BREAK_US / 1_000_000.0)

            # 2. Mark After Break (MAB, minimum 8us)
            self._ser.break_condition = False
            time.sleep(config.DMX_MAB_US / 1_000_000.0)

            # 3. Transmit Start Code (0x00) + 512 channels
            packet = b"\x00" + frame[: config.UNIVERSE_SIZE]
            self._ser.write(packet)
            self._ser.flush()
            self._frames_sent += 1
            return True
        except Exception as e:
            self._last_error = f"Write error: {str(e)}"
            self.close()
            return False

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "driver_name": "Enttec Open DMX USB (FTDI FT232R)",
            "connected": self.is_connected(),
            "configured_port": self.requested_port,
            "actual_port": self.actual_port,
            "baudrate": config.SERIAL_BAUDRATE,
            "frames_sent": self._frames_sent,
            "last_error": self._last_error,
            "latency_timer_ms": self._latency_timer_val,
            "status": "connected" if self.is_connected() else "disconnected",
        }


class DMXHardwareDaemon:
    """
    Continuous background DMX frame transmission daemon.
    Polls the mixer buffer at 35 - 44 Hz and writes full 512-byte frames to the active driver.
    """

    def __init__(self, mixer: Optional[DMXMixer] = None, driver_type: str = config.DEFAULT_DRIVER):
        self.mixer = mixer or get_mixer()
        self.driver_type = driver_type
        self.driver: BaseDMXDriver = VirtualDMXDriver()
        self.target_fps = config.DEFAULT_FPS
        self.actual_fps = 0.0
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.total_cycles = 0

        self.set_driver(self.driver_type)

    def set_driver(self, driver_type: str, port: Optional[str] = None) -> bool:
        with self._lock:
            old_driver = self.driver
            if old_driver:
                old_driver.close()

            self.driver_type = driver_type
            if driver_type == "enttec_open":
                candidate = EnttecOpenDMXDriver(port=port)
                if candidate.open():
                    self.driver = candidate
                    return True
                else:
                    # Fallback to Virtual
                    self.driver = VirtualDMXDriver()
                    self.driver.open()
                    return False
            else:
                self.driver = VirtualDMXDriver()
                self.driver.open()
                return True

    def set_fps(self, fps: int) -> None:
        clamped = max(config.MIN_FPS, min(config.MAX_FPS, int(fps)))
        self.target_fps = clamped

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, name="DMXHardwareDaemon", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        with self._lock:
            if self.driver:
                self.driver.close()

    def _run_loop(self) -> None:
        frame_window_start = time.time()
        frames_in_window = 0

        while not self._stop_event.is_set():
            loop_start = time.time()
            target_period = 1.0 / float(self.target_fps)

            # 1. Grab snapshot from mixer
            raw_frame = self.mixer.get_frame()

            # 2. Transmit via active driver
            ok = self.driver.send_frame(raw_frame)
            if not ok and self.driver_type == "enttec_open":
                # Auto-failover to Virtual driver if hardware disconnects
                with self._lock:
                    self.driver = VirtualDMXDriver()
                    self.driver.open()

            self.total_cycles += 1
            frames_in_window += 1

            # 3. Calculate running FPS every 1 second
            now = time.time()
            if now - frame_window_start >= 1.0:
                self.actual_fps = round(frames_in_window / (now - frame_window_start), 1)
                frames_in_window = 0
                frame_window_start = now

            # 4. High-precision pacing
            elapsed = time.time() - loop_start
            sleep_time = target_period - elapsed
            if sleep_time > 0.001:
                time.sleep(sleep_time)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            diag = self.driver.get_diagnostics() if self.driver else {}
            return {
                "running": self._running,
                "target_fps": self.target_fps,
                "actual_fps": self.actual_fps,
                "total_cycles": self.total_cycles,
                "driver_mode": self.driver_type,
                "driver_diagnostics": diag,
            }


def get_hardware_daemon() -> DMXHardwareDaemon:
    """Singleton getter for the hardware output daemon."""
    global _global_daemon_instance
    if _global_daemon_instance is None:
        with _daemon_lock:
            if _global_daemon_instance is None:
                _global_daemon_instance = DMXHardwareDaemon()
                _global_daemon_instance.start()
    return _global_daemon_instance
