-- Application Settings & Credentials
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fixture Definition & Patch
CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    model TEXT,
    manufacturer TEXT,
    start_channel INTEGER NOT NULL CHECK(start_channel BETWEEN 1 AND 512),
    channel_count INTEGER NOT NULL CHECK(channel_count > 0 AND channel_count <= 512),
    group_tag TEXT DEFAULT 'general',
    is_active INTEGER DEFAULT 1,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual Channel Mapping per Fixture
CREATE TABLE IF NOT EXISTS fixture_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    channel_offset INTEGER NOT NULL, -- 0-based offset from start_channel
    channel_type TEXT NOT NULL,      -- 'dimmer', 'red', 'green', 'blue', 'white', 'pan', 'tilt', 'strobe', etc.
    label TEXT NOT NULL,
    default_value INTEGER DEFAULT 0 CHECK(default_value BETWEEN 0 AND 255),
    FOREIGN KEY(fixture_id) REFERENCES fixtures(id) ON DELETE CASCADE
);

-- Static Presets (Scenes)
CREATE TABLE IF NOT EXISTS presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT DEFAULT 'custom',
    channel_payload TEXT NOT NULL,   -- JSON object: {"dmx_ch": value, ...}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Show Scripts (Dynamic Procedural Routines)
CREATE TABLE IF NOT EXISTS show_scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    footprint_channels TEXT NOT NULL,-- JSON list of affected DMX channels: [1, 2, 3...]
    python_code TEXT NOT NULL,       -- Executable generator code
    is_favorite INTEGER DEFAULT 0,
    ui_page INTEGER DEFAULT 1,       -- Pagination index for live busking screen
    created_by_ai INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI Fixture Wizard Diagnostic Logs
CREATE TABLE IF NOT EXISTS wizard_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_name TEXT,
    start_channel INTEGER,
    channel_count INTEGER,
    status TEXT DEFAULT 'in_progress', -- 'in_progress', 'completed', 'aborted'
    transcript TEXT,                   -- JSON list of diagnostic steps, user feedback, and channel sets
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI Doctor & Self-Healing Telemetry Logs
CREATE TABLE IF NOT EXISTS health_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,          -- 'hardware', 'permissions', 'database', 'script'
    severity TEXT NOT NULL,          -- 'info', 'warning', 'critical'
    message TEXT NOT NULL,
    details TEXT,                    -- JSON error trace, environment info, or diagnosis
    remediated INTEGER DEFAULT 0,    -- 0=unresolved, 1=auto-repaired
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_fixtures_start_channel ON fixtures(start_channel);
CREATE INDEX IF NOT EXISTS idx_fixture_channels_fixture ON fixture_channels(fixture_id);
CREATE INDEX IF NOT EXISTS idx_show_scripts_ui_page ON show_scripts(ui_page);
CREATE INDEX IF NOT EXISTS idx_health_logs_created ON health_logs(created_at);
