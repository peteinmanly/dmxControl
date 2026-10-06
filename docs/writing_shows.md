# Writing Dynamic Python Show Scripts

Show scripts are procedural routines written in standard Python that generate animated visual lighting effects.

## 1. Script Execution Context
Every script runs in an isolated worker thread with injected helper objects:
- `dmx.set(channel: int, value: int)`: Sets channel level (0-255). Restricted to the script's registered footprint.
- `dmx.get(channel: int) -> int`: Reads current channel level.
- `stop_event`: A `threading.Event` instance. Your loop MUST check `while not stop_event.is_set():`.
- `time`: Standard time functions (`time.time()`, `time.sleep()`). The `time.sleep(dt)` call is dynamically scaled by the global Speed Multiplier (0.25x to 4.0x) and Tap Tempo controls, allowing live beat synchronization without modifying script source code.
- `math`: Standard math library (`sin`, `cos`, `radians`, `pi`, etc.).
- `random`: Random number generators.

## 2. Example: Multi-Channel Sine Wave
```python
import math
import time

step = 0.0
# Animates channels 1 through 4
while not stop_event.is_set():
    r = int((math.sin(step) + 1.0) * 127.5)
    g = int((math.sin(step + 2.09) + 1.0) * 127.5)
    b = int((math.sin(step + 4.18) + 1.0) * 127.5)
    
    dmx.set(1, r)
    dmx.set(2, g)
    dmx.set(3, b)
    dmx.set(4, 255)  # Dimmer full
    
    step += 0.05
    time.sleep(0.025)  # ~40 Hz update loop
```

## 3. AST Security Constraints
To ensure application stability and safety on host systems:
- Imports other than `math`, `time`, and `random` are strictly prohibited.
- Calls to `eval()`, `exec()`, `open()`, or OS system calls are blocked by the AST validator before execution.
- Loops that do not test `stop_event` or omit `time.sleep()` are rejected to prevent thread lockups.
