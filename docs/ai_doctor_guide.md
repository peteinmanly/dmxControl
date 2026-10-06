# AI Doctor & Terminal Troubleshooter Guide

The controller includes an intelligent diagnostics framework powered by **Gemini 3.8 Flash** that resolves system contention, hardware misconfigurations, and script runtime exceptions.

## 1. The Background "AI Doctor"
The AI Doctor (`ai/self_healing.py`) continuously monitors telemetry across five domains:
1. **Serial Hardware**: Port connectivity, transmission write timeouts, and driver errors.
2. **User Permissions**: Validates `dialout` group membership for non-root serial access.
3. **Conflicting Daemons**: Checks for `brltty` or other processes locking `/dev/ttyUSB0`.
4. **Database Integrity**: Runs SQLite `PRAGMA integrity_check` and runs automated schema repairs if needed.
5. **Script Runtimes**: Detects exceptions in running show threads (e.g., divide by zero, out-of-bounds channels).

### Health Status Badges
- **HEALTHY** (Green): All subsystems operating within normal parameters.
- **DEGRADED** (Yellow): Controller running with fallback options (e.g. running Virtual DMX because no USB cable is connected).
- **CRITICAL** (Red): Permission denial, port collision, or DB error blocking output.

## 2. Interactive Terminal Troubleshooter (Settings Tab)
When encountering physical lighting anomalies, open the **Interactive AI Terminal Troubleshooter** under the Settings tab:

1. **Describe the Problem**:
   Type what is happening in plain English (e.g., *"Fixtures flickered when starting the color chase"*).
   Or click one of the quick diagnostic recipes:
   - 🔍 *Audit USB & Drivers*
   - 👤 *Check dialout Permissions*
   - 🚫 *Check brltty Conflicts*
   - ⏱️ *Check Latency & Logs*
2. **Generate Command**:
   Gemini formulates a read-only, non-destructive Linux Mint bash command pipeline.
3. **Run in Terminal**:
   Click **Copy**, paste into your terminal, run the command, and copy the terminal output.
4. **Analyze Output**:
   Paste the output back into the interface and click **Analyze Terminal Output**. Gemini explains the root cause in plain English and generates exact, copy-paste solution commands with verification steps.
