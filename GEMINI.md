# Project Guide: AI-Assisted DMX Web Controller

## 1. Overview & Purpose
This codebase is an open-source, web-based, AI-assisted DMX512 lighting controller designed for live busking, gig productions, and dynamic architectural lighting. It runs as a lightweight Python FastAPI application connected to physical DMX lighting fixtures via an **ENTTEC Open DMX USB** interface, with full remote busking support for iPads and tablets over local Wi-Fi.

---

## 2. Linux Mint & Hardware Connectivity (The Rig)
When running on the Linux Mint laptop connected to the lights:

### Hardware Architecture:
- **Interface**: ENTTEC Open DMX USB (FTDI FT232R USB-to-UART chip connected to an RS485 transceiver).
- **Device Node**: Usually `/dev/ttyUSB0` or `/dev/serial/by-id/usb-FTDI_...`.
- **Timing Model**: Host CPU bit-bangs the DMX frame:
  - Break: $\ge 88\,\mu\text{s}$ (our driver uses $100\,\mu\text{s}$).
  - Mark After Break (MAB): $\ge 8\,\mu\text{s}$ (our driver uses $12\,\mu\text{s}$).
  - Baudrate: 250,000 baud, 8N2.
  - Refresh Rate: 40 Hz continuous stream.

### Linux Mint Setup & Troubleshooting:
1. **Serial Port Permissions (`dialout`)**:
   ```bash
   sudo usermod -a -G dialout $USER
   newgrp dialout
   ```
2. **Persistent Udev Rule**:
   Copy the provided rule so `/dev/ttyUSB*` has 0666 permissions and a consistent `/dev/enttec_open_dmx` symlink:
   ```bash
   sudo cp udev/99-ftdi.rules /etc/udev/rules.d/
   sudo udevadm control --reload-rules && sudo udevadm trigger
   ```
3. **Crucial Linux Mint Conflict (`brltty`)**:
   Linux Mint / Ubuntu often runs the `brltty` (Braille Terminal) daemon which automatically seizes FTDI serial adapters, causing `Device or resource busy` or vanishing device nodes.
   If `/dev/ttyUSB0` fails to open or is seized:
   ```bash
   sudo systemctl stop brltty
   sudo systemctl mask brltty
   ```
4. **Latency Timer (Jitter Elimination)**:
   For crisp 40 Hz DMX frame timing:
   ```bash
   echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
   ```
5. **Virtual Hardware Fallback**:
   If no USB DMX adapter is plugged in, the app automatically fails over to `VirtualDMXDriver` so the web UI, presets, and scripts remain 100% operational in mock mode.

---

## 3. Quickstart & Execution

### Starting the Server:
```bash
./run.sh
# OR directly with uvicorn:
./venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```
- Access locally: `http://localhost:8000`
- Access from an iPad on the same Wi-Fi: `http://<laptop-local-ip>:8000`

### Running the Test Suite:
```bash
./venv/bin/python3 -m unittest discover tests -v
```
All 38 automated unit tests test mixer math, script runner AST safety, crossfading, panic controls, repositories, and hardware fallback.

---

## 4. Architecture & Key Modules

```
├── app.py                      # FastAPI REST API & WebSocket (/ws/live) at 40 Hz
├── config.py                   # Global configuration, serial ports, DMX universe defaults
├── database/
│   ├── schema.sql              # SQLite schema (fixtures, presets, scripts, settings, health)
│   ├── db.py                   # DB connection & lifecycle
│   └── repositories.py         # Type-safe data access repositories
├── engine/
│   ├── hardware.py             # HardwareDaemon, EnttecOpenDMXDriver, VirtualDMXDriver
│   ├── mixer.py                # 512-channel DMXMixer, crossfader, grand master, blackout
│   └── script_runner.py        # Sandboxed procedural Python runner with AST safety & tap tempo
├── ai/
│   ├── gemini_client.py        # Google Gemini 3.8 Flash SDK integration
│   ├── fixture_wizard.py       # Conversational fixture patching wizard
│   ├── self_healing.py         # AI Doctor telemetry diagnostic & healing system
│   ├── show_generator.py       # Natural language -> procedural lighting script generator
│   └── terminal_troubleshooter.py # Diagnoses Linux OS / USB issues and generates fix commands
├── templates/
│   └── index.html              # Single-page UI with Split View & Fullscreen Busking
└── static/
    ├── css/style.css           # Dark theme, tablet touch ergonomics, vertical fader
    └── js/
        ├── api.js              # Standard fetch wrapper for REST endpoints
        ├── live_control.js     # Presets, show scripts, vertical Grand Master fader, fullscreen
        ├── fixtures.js         # Fixture patching table & AI wizard modal
        └── settings.js         # Hardware config, AI Doctor diagnostics, iPad modal
```

---

## 5. Live Busking & UI Conventions

1. **Grand Master Fader**:
   - Vertical full-height fader docked on the right side of the screen.
   - Live scaling factor (`0.0` to `1.0`), smoothly scales all 512 channels without altering the underlying scene colors.
   - Includes quick-snap buttons: `FULL` (100%) and `ZERO` (0%).
2. **Display Modes (Split vs Fullscreen)**:
   - **Split View**: Shows Presets and Procedural Show Scripts side-by-side with the 512-channel ownership matrix.
   - **Pure Fullscreen Presets**: Hides the navbar, toolbar, and matrix to present **only the Static Presets and the Master Fader** on screen—ideal for iPad busking.
   - **Exit Fullscreen**: Tapping `⤺ Exit Fullscreen` or pressing `Escape` instantly returns to Split View.
   - **Zero Network/DMX Traffic Invariant**: Switching fullscreen modes is strictly a client-side CSS presentation toggle; it NEVER triggers DMX output or API requests.
3. **Panic Controls**:
   - **Blackout**: Immediately drops all 512 channels to 0 and stops active crossfades. Selecting a preset afterwards restores lighting immediately.
   - **Kill Effects**: Immediately terminates all background procedural scripts while leaving static preset looks intact.

---

## 6. Procedural Show Scripts & Safety Rules
Procedural scripts allow algorithmic effects (color chasers, rainbow waves, strobes, breathing washes) written in standard Python.
- **AST Safety Validation**: Every script is inspected before execution by `ASTSafetyValidator` in `engine/script_runner.py`.
- **Forbidden**: `eval`, `exec`, arbitrary `import`, filesystem access, subprocesses, infinite loops without `stop_event.is_set()` and `sleep()`.
- **Allowed Environment**: `mixer`, `universe`, `fixtures`, `time`, `math`, `random`, `stop_event`.
- **Cooperative Concurrency**: Scripts that modify separate channels run simultaneously. If a script collides with active channels of another script, the earlier script is halted cleanly to avoid fixture flicker.
