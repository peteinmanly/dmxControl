"""
Configuration and Defaults for AI-Assisted DMX Web Controller.
Optimized for Linux Mint host with Enttec Open DMX USB interface.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "dmx_controller.db"

STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# DMX512 Timing & Frame Configuration
UNIVERSE_SIZE = 512
DEFAULT_FPS = 40  # Standard DMX frame rate (35 - 44 Hz)
MIN_FPS = 20
MAX_FPS = 44

# Enttec Open DMX USB (FTDI FT232R) Serial Specifications
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
SERIAL_BAUDRATE = 250000  # Standard DMX512 baud rate
SERIAL_STOPBITS = 2       # 8N2
SERIAL_DATABITS = 8
SERIAL_PARITY = "N"

# Break & Mark-After-Break (MAB) Timing in microseconds
DMX_BREAK_US = 100  # Minimum 88us
DMX_MAB_US = 12     # Minimum 8us

# Driver Modes: "enttec_open", "virtual"
DEFAULT_DRIVER = "enttec_open"

# Script Execution Arbitration
SCRIPT_KILL_TIMEOUT_SEC = 0.25  # 250ms hard-kill timeout for overlapping footprints

# Gemini AI Defaults
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
GEMINI_API_KEY_ENV = os.getenv("GEMINI_API_KEY", "")

# Web Server Defaults
SERVER_HOST = os.getenv("DMX_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("DMX_PORT", "8000"))
