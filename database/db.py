"""
SQLite database engine, connection manager, migration, and seeder.
"""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

import config

_db_lock = threading.Lock()
_global_db_instance: Optional["Database"] = None


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else config.DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_database()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a configured sqlite3 connection with Row factory and foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def init_database(self) -> None:
        """Initializes tables from schema.sql and seeds default data if newly created."""
        with _db_lock:
            schema_file = config.BASE_DIR / "database" / "schema.sql"
            with open(schema_file, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            conn = self.get_connection()
            try:
                conn.executescript(schema_sql)
                conn.commit()
                self._seed_defaults(conn)
            finally:
                conn.close()

    def check_integrity(self) -> Dict[str, Any]:
        """Runs PRAGMA integrity_check on the database."""
        with _db_lock:
            conn = self.get_connection()
            try:
                cursor = conn.execute("PRAGMA integrity_check;")
                result = cursor.fetchall()
                is_ok = len(result) == 1 and result[0][0].lower() == "ok"
                return {
                    "ok": is_ok,
                    "details": [r[0] for r in result],
                }
            except Exception as e:
                return {
                    "ok": False,
                    "details": [str(e)],
                }
            finally:
                conn.close()

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        """Seeds initial settings, sample fixtures, presets, and procedural scripts."""
        # 1. Default Settings
        default_settings = [
            ("driver", config.DEFAULT_DRIVER),
            ("serial_port", config.DEFAULT_SERIAL_PORT),
            ("fps", str(config.DEFAULT_FPS)),
            ("gemini_model", config.DEFAULT_GEMINI_MODEL),
            ("gemini_api_key", config.GEMINI_API_KEY_ENV),
        ]
        for key, val in default_settings:
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);",
                (key, val),
            )

        # 2. Seed Sample Fixture if table is empty
        cursor = conn.execute("SELECT COUNT(*) FROM fixtures;")
        if cursor.fetchone()[0] == 0:
            # 4-channel RGBW Par (Address 1..4)
            cursor = conn.execute(
                """
                INSERT INTO fixtures (name, model, manufacturer, start_channel, channel_count, group_tag, notes)
                VALUES ('Front Stage Left', 'RGBW 4CH Par', 'Generic', 1, 4, 'front_wash', '4-channel RGBW wash');
                """
            )
            par1_id = cursor.lastrowid
            channels_par1 = [
                (par1_id, 0, "red", "Red", 0),
                (par1_id, 1, "green", "Green", 0),
                (par1_id, 2, "blue", "Blue", 0),
                (par1_id, 3, "white", "White", 0),
            ]
            conn.executemany(
                """
                INSERT INTO fixture_channels (fixture_id, channel_offset, channel_type, label, default_value)
                VALUES (?, ?, ?, ?, ?);
                """,
                channels_par1,
            )

            # 4-channel RGBW Par (Address 5..8)
            cursor = conn.execute(
                """
                INSERT INTO fixtures (name, model, manufacturer, start_channel, channel_count, group_tag, notes)
                VALUES ('Front Stage Right', 'RGBW 4CH Par', 'Generic', 5, 4, 'front_wash', '4-channel RGBW wash');
                """
            )
            par2_id = cursor.lastrowid
            channels_par2 = [
                (par2_id, 0, "red", "Red", 0),
                (par2_id, 1, "green", "Green", 0),
                (par2_id, 2, "blue", "Blue", 0),
                (par2_id, 3, "white", "White", 0),
            ]
            conn.executemany(
                """
                INSERT INTO fixture_channels (fixture_id, channel_offset, channel_type, label, default_value)
                VALUES (?, ?, ?, ?, ?);
                """,
                channels_par2,
            )

        # 3. Seed Default Presets if empty
        cursor = conn.execute("SELECT COUNT(*) FROM presets;")
        if cursor.fetchone()[0] == 0:
            sample_presets = [
                (
                    "Warm White Wash",
                    "Full front warm white wash",
                    "wash",
                    json.dumps({"1": 200, "2": 160, "3": 80, "4": 255, "5": 200, "6": 160, "7": 80, "8": 255}),
                ),
                (
                    "Cyan & Blue Atmospheric",
                    "Deep ocean wash for dramatic stages",
                    "color",
                    json.dumps({"1": 0, "2": 220, "3": 255, "4": 0, "5": 0, "6": 100, "7": 255, "8": 0}),
                ),
                (
                    "Fiery Amber & Red",
                    "Warm punchy concert look",
                    "color",
                    json.dumps({"1": 255, "2": 45, "3": 0, "4": 40, "5": 255, "6": 90, "7": 0, "8": 20}),
                ),
                (
                    "All Fixtures Off",
                    "Zero out patched fixtures",
                    "utility",
                    json.dumps({"1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0}),
                ),
            ]
            conn.executemany(
                """
                INSERT INTO presets (name, description, category, channel_payload)
                VALUES (?, ?, ?, ?);
                """,
                sample_presets,
            )

        # 4. Seed Default Procedural Show Scripts if empty
        cursor = conn.execute("SELECT COUNT(*) FROM show_scripts;")
        if cursor.fetchone()[0] == 0:
            sample_scripts = [
                (
                    "Color Sine Wave",
                    "Smooth undulating RGB color sweep across front wash fixtures",
                    json.dumps([1, 2, 3, 4, 5, 6, 7, 8]),
                    '''# Smooth sine wave oscillation across channels 1..8
import math
import time

step = 0
while not stop_event.is_set():
    r = int((math.sin(step) + 1.0) * 127.5)
    g = int((math.sin(step + 2.094) + 1.0) * 127.5)
    b = int((math.sin(step + 4.188) + 1.0) * 127.5)
    
    # Left Par (Channels 1..4)
    dmx.set(1, r)
    dmx.set(2, g)
    dmx.set(3, b)
    dmx.set(4, 0)
    
    # Right Par (Channels 5..8 - Phase offset)
    dmx.set(5, b)
    dmx.set(6, r)
    dmx.set(7, g)
    dmx.set(8, 0)
    
    step += 0.05
    time.sleep(0.025)
''',
                    1,
                    1,
                    0,
                ),
                (
                    "Pulsing White Dimmer",
                    "Breathing white wash effect",
                    json.dumps([4, 8]),
                    '''# White channel breathing pulse
import math
import time

angle = 0.0
while not stop_event.is_set():
    val = int((math.sin(angle) + 1.0) * 127.5)
    dmx.set(4, val)
    dmx.set(8, val)
    angle += 0.08
    time.sleep(0.03)
''',
                    0,
                    1,
                    0,
                ),
            ]
            conn.executemany(
                """
                INSERT INTO show_scripts (name, description, footprint_channels, python_code, is_favorite, ui_page, created_by_ai)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                sample_scripts,
            )

        conn.commit()

    def export_backup_json(self) -> Dict[str, Any]:
        """Exports all database tables into a clean JSON dictionary for backup."""
        with _db_lock:
            conn = self.get_connection()
            try:
                tables = ["settings", "fixtures", "fixture_channels", "presets", "show_scripts", "wizard_sessions", "health_logs"]
                backup_data: Dict[str, Any] = {}
                for tbl in tables:
                    cursor = conn.execute(f"SELECT * FROM {tbl};")
                    cols = [col[0] for col in cursor.description]
                    rows = [dict(zip(cols, row)) for row in cursor.fetchall()]
                    backup_data[tbl] = rows
                return backup_data
            finally:
                conn.close()

    def reset_factory_defaults(self) -> None:
        """Wipes the database and re-initializes factory default settings and seed items."""
        with _db_lock:
            conn = self.get_connection()
            try:
                conn.execute("PRAGMA foreign_keys = OFF;")
                tables = ["settings", "fixtures", "fixture_channels", "presets", "show_scripts", "wizard_sessions", "health_logs"]
                for tbl in tables:
                    conn.execute(f"DROP TABLE IF EXISTS {tbl};")
                conn.commit()
            finally:
                conn.close()
        self.init_database()


def get_db(db_path: Optional[Path] = None) -> Database:
    """Singleton getter for the Database instance."""
    global _global_db_instance
    if _global_db_instance is None:
        _global_db_instance = Database(db_path)
    return _global_db_instance
