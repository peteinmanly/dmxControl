# System Architecture & Threading Model

## 1. Playback Arbitration: Option 2 (Non-Overlapping Partitions)
To ensure reliable live busking without flickering or race conditions between multiple effects, the controller implements **Fixture-Aware Scoping with Non-Overlapping Partitions**:

1. **Hardware Daemon Thread (`DMXHardwareDaemon`)**:
   - Sole owner of the serial port/FTDI device.
   - Loops at a steady 35–44 Hz (~25ms interval).
   - Reads the in-memory 512-byte buffer and transmits the complete frame.
2. **Mixer Buffer (`DMXMixer`)**:
   - In-memory `bytearray(512)` managed with `threading.Lock`.
   - Tracks channel ownership for all 512 channels (`None`, `Preset:<id>`, or `Script:<id>`).
3. **Script Execution Threads (`ScriptRunner`)**:
   - Each procedural show routine runs in its own isolated Python thread.
   - When a routine triggers on footprint $\mathcal{F}$, the arbiter detects any running routines $S_k$ whose footprint intersects $\mathcal{F}$.
   - Colliding routines receive a cooperative `stop_event.set()` signal and are given 250ms to cleanly terminate before ownership is transferred.
   - Independent routines running on disjoint channels execute simultaneously.

## 2. Real-Time WebSocket Diagnostics
- The application exposes `/ws/universe`, transmitting 512 channel levels and ownership states to the web browser at ~30 Hz.
- The browser UI renders this in the 512-channel diagnostic grid and partition matrix with zero REST polling overhead.
