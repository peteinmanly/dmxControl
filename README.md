# 💡 AI-Assisted DMX Web Controller

[![Platform: Linux Mint](https://img.shields.io/badge/Platform-Linux%20Mint%20%7C%20Debian%20%7C%20Ubuntu-brightgreen.svg)](https://linuxmint.com/)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Hardware: Enttec Open DMX USB](https://img.shields.io/badge/Hardware-Enttec%20Open%20DMX%20USB-orange.svg)](https://www.enttec.com/)
[![AI: Google Gemini 3.8 Flash](https://img.shields.io/badge/AI-Gemini%203.8%20Flash-purple.svg)](https://ai.google.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A production-grade, local web-based lighting controller engineered for **Linux Mint** hosts using the **Enttec Open DMX USB** interface (and virtual/dummy fallback). Features fixture-aware channel partition arbitration, an embedded zero-configuration SQLite store, a real-time 40 Hz dark-mode busking dashboard, and an integrated **Gemini AI Engine** for automated fixture reverse-engineering, AST-validated procedural show generation, self-healing diagnostics, and an interactive terminal troubleshooter.

---

## 📋 Platform Compatibility Matrix

| Operating System | Support Tier | Hardware Access | Notes |
|---|---|---|---|
| **Linux Mint 21.x / 22.x** | **Tier 1 (Primary Target)** | Enttec Open DMX / FTDI (`/dev/ttyUSB*`) | Native host. Full support with automated `brltty` and `dialout` checks. |
| **Ubuntu 22.04 / 24.04 LTS** | **Tier 1 (Production)** | Enttec Open DMX / FTDI (`/dev/ttyUSB*`) | Identical upstream base; plug-and-play. |
| **Debian 11 / 12** | **Tier 1 (Production)** | Enttec Open DMX / FTDI (`/dev/ttyUSB*`) | Excellent for headless lighting appliances. |
| **Raspberry Pi OS (Bookworm)**| **Tier 1 (Embedded)** | Enttec Open DMX / FTDI (`/dev/ttyUSB*`) | Dedicated Pi 4 & Pi 5 lighting consoles. |
| **macOS (12+)** | **Tier 2 (Development/Dev)** | Virtual / FTDI VCP (`/dev/cu.usbserial*`) | Excellent for programming presets and offline testing. |
| **Windows 10 / 11** | **Tier 2 (Development/Dev)** | Virtual / COM Ports | Run via Native Python or WSL2 with usbipd-win. |

---

## ⚡ Quickstart (Under 5 Minutes)

### 1. Install System Dependencies (Linux Mint / Debian / Ubuntu)
```bash
sudo apt update && sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    python3-dev \
    libftdi1-2 \
    libftdi1-dev \
    udev \
    usbutils
```

### 2. Configure USB Permissions & Udev Rules
To allow non-root users to communicate with the Enttec Open DMX USB adapter:
```bash
# Add current user to the dialout group
sudo usermod -a -G dialout $USER

# Install udev rule for FTDI FT232R USB-to-DMX cables
sudo cp udev/99-ftdi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger

# Apply group changes immediately
newgrp dialout
```

> [!TIP]
> **Linux Mint Conflict Fix**: If `/dev/ttyUSB0` disconnects or is reported busy, Linux Mint's Braille service (`brltty`) may have grabbed the FTDI chip. Run:
> `sudo systemctl stop brltty && sudo systemctl mask brltty`

### 3. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/peteinmanly/dmxControl.git
cd dmxControl

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Launch Application
```bash
python3 -m uvicorn app:app --host 0.0.0.0 --port 8000
```
Open your browser at **`http://localhost:8000`**.

---

## ✨ Key Features & Architecture

```
 ┌─────────────────────────────────────────────────────────────┐
 │                    Web Client (Browser)                     │
 │  ┌─────────────────┬─────────────────┬────────────────────┐ │
 │  │  Live Dashboard │ Fixtures & Patch│ Settings & Gemini  │ │
 │  │ (Presets/Shows) │ (Wizard & CRUD) │  (AI Doctor & Term)│ │
 │  └────────┬────────┴────────┬────────┴─────────┬──────────┘ │
 └───────────┼─────────────────┼──────────────────┼────────────┘
             │ WebSocket / 40Hz│ REST Endpoints   │
 ┌───────────▼─────────────────▼──────────────────▼────────────┐
 │                  FastAPI Backend Application                │
 │  ┌───────────────────────────────────────────────────────┐  │
 │  │ Engine Coordinator & Playback Arbiter                 │  │
 │  │ - Fixture-aware non-overlapping channel partitions    │  │
 │  │ - Isolated Python Show execution threads              │  │
 │  │ - Cooperative cancellation with 250ms hard-kill       │  │
 │  └────────────┬────────────────────────────┬─────────────┘  │
 │               │                            │                │
 │  ┌────────────▼──────────────┐  ┌──────────▼─────────────┐  │
 │  │ Gemini AI Service Layer   │  │ SQLite Database Layer  │  │
 │  │ - AI Doctor Self-Healing  │  │ - Zero-config schema   │  │
 │  │ - Terminal Troubleshooter │  │ - Fixtures & Patches   │  │
 │  │ - Channel Probing Wizard  │  │ - Presets & Show Codes │  │
 │  │ - AST Show Generator      │  │ - Health & Event Logs  │  │
 │  └────────────┬──────────────┘  └────────────────────────┘  │
 │               │                                             │
 │  ┌────────────▼──────────────────────────────────────────┐  │
 │  │ Shared In-Memory Buffer & Arbiter Table (Zero-Latency)│  │
 │  │ - 512-byte raw frame & channel ownership lock         │  │
 │  └──────────────────────────┬────────────────────────────┘  │
 │                             │                               │
 │  ┌──────────────────────────▼────────────────────────────┐  │
 │  │ Enttec Open DMX / Hardware Output Daemon (~35-44 Hz)  │  │
 │  │ - Software-timed Serial Break (100µs) + MAB (12µs)    │  │
 │  │ - Auto-fallback to Virtual DMX if cable is detached   │  │
 │  └───────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────┘
```

### 1. Fixture-Aware Playback Arbitration
- Resolves busking contention using **Option 2: Non-Overlapping Channel Partitions**.
- When a show script or preset triggers on footprint $\mathcal{F}$, any active scripts colliding with $\mathcal{F}$ receive a cooperative `stop_event` signal and terminate within 250ms.
- Disjoint scripts running on non-overlapping channels execute concurrently without interference.

### 2. Enttec Open DMX Hardware Output (~40 Hz)
- Emits exact DMX512 timing via FTDI FT232R serial: $100\,\mu\text{s}$ break, $12\,\mu\text{s}$ Mark-After-Break (MAB), and start byte `0x00` followed by 512 channel values at 250,000 baud 8N2.
- Inspects and tunes the Linux kernel FTDI latency timer (`latency_timer` $\rightarrow$ 1ms) for jitter-free output.
- Auto-failover to **Virtual DMX** if the hardware interface is unplugged.

### 3. AI Doctor & Automated Self-Healing
- Continuously monitors serial port connectivity, user group permissions, conflicting system daemons (`brltty`), database integrity, and script exceptions.
- Consults Gemini 3.8 Flash to diagnose root causes and executes safe automated repairs (port re-binding, driver recovery, DB schema integrity).

### 4. Interactive AI Terminal Troubleshooter (Settings Tab)
- Describe any symptom in plain English (e.g. *"The Enttec LED is flashing green but fixtures don't react"*).
- The AI synthesizes a safe, non-destructive Linux Mint terminal command pipeline with a 1-click **Copy Command** button.
- Paste your terminal output back into the interface, and Gemini provides a plain-English diagnosis, copy-paste remediation commands, and verification steps.
- Includes 1-click quick diagnostic recipes for USB hardware audits, permission checks, `brltty` detection, and latency timer inspection.

### 5. AI Fixture Wizard (Reverse-Engineering Unknown Fixtures)
- **Path A (Documentation Lookup)**: Paste user manual snippets or dipswitch charts to generate instant patch profiles.
- **Path B (Interactive Probing Wizard)**: The wizard zeros the fixture's DMX block and iteratively manipulates individual channels (dimmer, colors, pan/tilt), asking natural questions and deducing the fixture's channel mapping from your physical observations.

### 6. Dynamic Procedural Show Generator with AST Safety
- Prompt Gemini to generate complex animated lighting routines (e.g. *"Create an undulating ocean wave chase across front wash fixtures"*).
- Validated via Python Abstract Syntax Tree (AST) analysis: restricts code to math, time, and scoped DMX commands; forbids unauthorized imports, file I/O, and shell execution.

### 7. Live Busking Performance Controls
- **Grand Master Intensity Fader**: Dedicated hardware-grade master fader (0–100%) in the top header. Proportionally scales all 512 DMX channel levels at 40 Hz without altering stored preset values or base fixture states.
- **Preset Smooth Crossfades**: Switch between static color washes and scenes with smooth linear interpolation over selectable fade times (**Cut**, **1s**, **2s**, **3s**, **5s**) running at 40 Hz.
- **Script Speed Multiplier & Tap Tempo**: Real-time tempo synchronization (0.25x to 4.0x) for looping procedural show routines. Features an interactive **🥁 Tap Tempo** button calculating live BPM (40–240 BPM) to sync looping color fades and chases to live musical performance on the fly.

---

## 🛠️ Configuration & Gemini API

1. In the Web UI, navigate to **Settings & Diagnostics**.
2. Enter your **Google Gemini API Key** and select `gemini-3.8-flash`. Click **Save Gemini Settings**.
3. Alternatively, export the key in your terminal environment:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   ```

---

## 🧪 Testing

Run the built-in test suite (zero external test dependencies required):
```bash
python3 -m unittest discover tests -v
```

---

## 📄 Documentation

- [Linux Hardware Setup & Udev Rules](docs/hardware_setup.md)
- [AI Doctor & Terminal Troubleshooter Guide](docs/ai_doctor_guide.md)
- [System Architecture & Threading Model](docs/architecture.md)
- [SQLite Schema & Backup Guide](docs/database.md)
- [AI Fixture Reverse-Engineering Guide](docs/ai_wizard_guide.md)
- [Writing Dynamic Python Show Scripts](docs/writing_shows.md)

---

## 📜 License

Distributed under the [MIT License](LICENSE).
