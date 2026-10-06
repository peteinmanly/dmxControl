# SQLite Database Schema & Management

The controller relies on an embedded SQLite database (`data/dmx_controller.db`) with foreign keys enabled and WAL (Write-Ahead Logging) mode.

## 1. Tables Overview
1. **`settings`**: Key-value application configurations (Gemini API key, model selection, driver choice, refresh rate).
2. **`fixtures`**: Patched lighting fixtures (name, start channel, channel count, group tag, notes).
3. **`fixture_channels`**: Detailed channel offsets per fixture (`dimmer`, `red`, `green`, `blue`, `pan`, `tilt`, `strobe`, etc.) with `ON DELETE CASCADE`.
4. **`presets`**: Static scene looks containing JSON channel payloads (`{"channel": value}`).
5. **`show_scripts`**: Procedural Python generator routines with footprint channel arrays and UI page assignments.
6. **`wizard_sessions`**: Transcripts of AI fixture discovery sessions.
7. **`health_logs`**: System telemetry, error events, and automated remediation actions.

## 2. Backup & Restore Workflows
- **One-Click JSON Export**: Accessible via **Settings & Diagnostics** -> `Export JSON Backup` (`GET /api/settings/backup`).
- **Direct Database Copy**: Because SQLite is a single self-contained file, you can back up your entire show database by copying `data/dmx_controller.db`.
- **Factory Reset**: Recreates the schema from `schema.sql` and re-seeds default wash fixtures and presets.
