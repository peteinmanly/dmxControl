"""
Data access repositories for fixtures, presets, show scripts, settings, wizard sessions, and health logs.
"""

import json
from typing import Dict, Any, List, Optional
from .db import Database, get_db


class SettingsRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?;", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()

    def set(self, key: str, value: str) -> None:
        conn = self.db.get_connection()
        try:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;
                """,
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all(self) -> Dict[str, str]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT key, value FROM settings;")
            return {row["key"]: row["value"] for row in cursor.fetchall()}
        finally:
            conn.close()

    def delete(self, key: str) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM settings WHERE key = ?;", (key,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class FixtureRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def get_all(self, active_only: bool = False) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            query = "SELECT * FROM fixtures"
            params = ()
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY start_channel ASC;"
            cursor = conn.execute(query, params)
            fixtures = [dict(row) for row in cursor.fetchall()]

            for fix in fixtures:
                c_cursor = conn.execute(
                    "SELECT * FROM fixture_channels WHERE fixture_id = ? ORDER BY channel_offset ASC;",
                    (fix["id"],),
                )
                fix["channels"] = [dict(c) for c in c_cursor.fetchall()]
            return fixtures
        finally:
            conn.close()

    def get_by_id(self, fixture_id: int) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM fixtures WHERE id = ?;", (fixture_id,))
            row = cursor.fetchone()
            if not row:
                return None
            fix = dict(row)
            c_cursor = conn.execute(
                "SELECT * FROM fixture_channels WHERE fixture_id = ? ORDER BY channel_offset ASC;",
                (fixture_id,),
            )
            fix["channels"] = [dict(c) for c in c_cursor.fetchall()]
            return fix
        finally:
            conn.close()

    def create(self, fixture_data: Dict[str, Any], channels: List[Dict[str, Any]]) -> int:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO fixtures (name, model, manufacturer, start_channel, channel_count, group_tag, is_active, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    fixture_data["name"],
                    fixture_data.get("model", ""),
                    fixture_data.get("manufacturer", ""),
                    int(fixture_data["start_channel"]),
                    int(fixture_data["channel_count"]),
                    fixture_data.get("group_tag", "general"),
                    fixture_data.get("is_active", 1),
                    fixture_data.get("notes", ""),
                ),
            )
            fixture_id = cursor.lastrowid

            for ch in channels:
                conn.execute(
                    """
                    INSERT INTO fixture_channels (fixture_id, channel_offset, channel_type, label, default_value)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (
                        fixture_id,
                        int(ch["channel_offset"]),
                        ch.get("channel_type", "dimmer"),
                        ch.get("label", f"Channel {ch['channel_offset'] + 1}"),
                        int(ch.get("default_value", 0)),
                    ),
                )
            conn.commit()
            return fixture_id
        finally:
            conn.close()

    def update(self, fixture_id: int, fixture_data: Dict[str, Any], channels: Optional[List[Dict[str, Any]]] = None) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE fixtures
                SET name = ?, model = ?, manufacturer = ?, start_channel = ?, channel_count = ?, group_tag = ?, is_active = ?, notes = ?
                WHERE id = ?;
                """,
                (
                    fixture_data["name"],
                    fixture_data.get("model", ""),
                    fixture_data.get("manufacturer", ""),
                    int(fixture_data["start_channel"]),
                    int(fixture_data["channel_count"]),
                    fixture_data.get("group_tag", "general"),
                    fixture_data.get("is_active", 1),
                    fixture_data.get("notes", ""),
                    fixture_id,
                ),
            )
            if cursor.rowcount == 0:
                return False

            if channels is not None:
                conn.execute("DELETE FROM fixture_channels WHERE fixture_id = ?;", (fixture_id,))
                for ch in channels:
                    conn.execute(
                        """
                        INSERT INTO fixture_channels (fixture_id, channel_offset, channel_type, label, default_value)
                        VALUES (?, ?, ?, ?, ?);
                        """,
                        (
                            fixture_id,
                            int(ch["channel_offset"]),
                            ch.get("channel_type", "dimmer"),
                            ch.get("label", f"Channel {ch['channel_offset'] + 1}"),
                            int(ch.get("default_value", 0)),
                        ),
                    )
            conn.commit()
            return True
        finally:
            conn.close()

    def delete(self, fixture_id: int) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM fixtures WHERE id = ?;", (fixture_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def toggle_active(self, fixture_id: int, is_active: bool) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("UPDATE fixtures SET is_active = ? WHERE id = ?;", (1 if is_active else 0, fixture_id))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class PresetRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def get_all(self) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM presets ORDER BY id ASC;")
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                try:
                    d["channel_payload"] = json.loads(d["channel_payload"])
                except Exception:
                    d["channel_payload"] = {}
                rows.append(d)
            return rows
        finally:
            conn.close()

    def get_by_id(self, preset_id: int) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM presets WHERE id = ?;", (preset_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["channel_payload"] = json.loads(d["channel_payload"])
            except Exception:
                d["channel_payload"] = {}
            return d
        finally:
            conn.close()

    def create(self, name: str, channel_payload: Dict[str, int], description: str = "", category: str = "custom") -> int:
        conn = self.db.get_connection()
        try:
            payload_str = json.dumps({str(k): int(v) for k, v in channel_payload.items()})
            cursor = conn.execute(
                """
                INSERT INTO presets (name, description, category, channel_payload)
                VALUES (?, ?, ?, ?);
                """,
                (name, description, category, payload_str),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update(self, preset_id: int, name: str, channel_payload: Dict[str, int], description: str = "", category: str = "custom") -> bool:
        conn = self.db.get_connection()
        try:
            payload_str = json.dumps({str(k): int(v) for k, v in channel_payload.items()})
            cursor = conn.execute(
                """
                UPDATE presets
                SET name = ?, description = ?, category = ?, channel_payload = ?
                WHERE id = ?;
                """,
                (name, description, category, payload_str, preset_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, preset_id: int) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM presets WHERE id = ?;", (preset_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class ShowScriptRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def get_all(self, page: Optional[int] = None) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            query = "SELECT * FROM show_scripts"
            params = ()
            if page is not None:
                query += " WHERE ui_page = ?"
                params = (page,)
            query += " ORDER BY is_favorite DESC, id ASC;"
            cursor = conn.execute(query, params)
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                try:
                    d["footprint_channels"] = json.loads(d["footprint_channels"])
                except Exception:
                    d["footprint_channels"] = []
                rows.append(d)
            return rows
        finally:
            conn.close()

    def get_by_id(self, script_id: int) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM show_scripts WHERE id = ?;", (script_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["footprint_channels"] = json.loads(d["footprint_channels"])
            except Exception:
                d["footprint_channels"] = []
            return d
        finally:
            conn.close()

    def create(
        self,
        name: str,
        footprint_channels: List[int],
        python_code: str,
        description: str = "",
        is_favorite: int = 0,
        ui_page: int = 1,
        created_by_ai: int = 0,
    ) -> int:
        conn = self.db.get_connection()
        try:
            footprint_str = json.dumps(sorted(list(set(int(ch) for ch in footprint_channels))))
            cursor = conn.execute(
                """
                INSERT INTO show_scripts (name, description, footprint_channels, python_code, is_favorite, ui_page, created_by_ai)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (name, description, footprint_str, python_code, is_favorite, ui_page, created_by_ai),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def update(
        self,
        script_id: int,
        name: Optional[str] = None,
        footprint_channels: Optional[List[int]] = None,
        python_code: Optional[str] = None,
        description: Optional[str] = None,
        is_favorite: Optional[int] = None,
        ui_page: Optional[int] = None,
    ) -> bool:
        conn = self.db.get_connection()
        try:
            current = self.get_by_id(script_id)
            if not current:
                return False

            n = name if name is not None else current["name"]
            desc = description if description is not None else current["description"]
            fps = footprint_channels if footprint_channels is not None else current["footprint_channels"]
            code = python_code if python_code is not None else current["python_code"]
            fav = is_favorite if is_favorite is not None else current["is_favorite"]
            page = ui_page if ui_page is not None else current["ui_page"]

            footprint_str = json.dumps(sorted(list(set(int(ch) for ch in fps))))

            cursor = conn.execute(
                """
                UPDATE show_scripts
                SET name = ?, description = ?, footprint_channels = ?, python_code = ?, is_favorite = ?, ui_page = ?
                WHERE id = ?;
                """,
                (n, desc, footprint_str, code, fav, page, script_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def delete(self, script_id: int) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM show_scripts WHERE id = ?;", (script_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


class WizardSessionRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def create_session(self, fixture_name: str, start_channel: int, channel_count: int) -> int:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO wizard_sessions (fixture_name, start_channel, channel_count, status, transcript)
                VALUES (?, ?, ?, 'in_progress', '[]');
                """,
                (fixture_name, start_channel, channel_count),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM wizard_sessions WHERE id = ?;", (session_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["transcript"] = json.loads(d["transcript"])
            except Exception:
                d["transcript"] = []
            return d
        finally:
            conn.close()

    def append_transcript_step(self, session_id: int, step_data: Dict[str, Any], status: str = "in_progress") -> bool:
        conn = self.db.get_connection()
        try:
            session = self.get_session(session_id)
            if not session:
                return False
            transcript = session["transcript"]
            transcript.append(step_data)
            cursor = conn.execute(
                """
                UPDATE wizard_sessions
                SET transcript = ?, status = ?
                WHERE id = ?;
                """,
                (json.dumps(transcript), status, session_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def clean_history(self) -> int:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM wizard_sessions;")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


class HealthLogRepository:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_db()

    def log(self, category: str, severity: str, message: str, details: Optional[Dict[str, Any]] = None, remediated: int = 0) -> int:
        conn = self.db.get_connection()
        try:
            details_str = json.dumps(details) if details else None
            cursor = conn.execute(
                """
                INSERT INTO health_logs (category, severity, message, details, remediated)
                VALUES (?, ?, ?, ?, ?);
                """,
                (category, severity, message, details_str, remediated),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("SELECT * FROM health_logs ORDER BY id DESC LIMIT ?;", (limit,))
            rows = []
            for r in cursor.fetchall():
                d = dict(r)
                if d["details"]:
                    try:
                        d["details"] = json.loads(d["details"])
                    except Exception:
                        pass
                rows.append(d)
            return rows
        finally:
            conn.close()

    def resolve(self, log_id: int) -> bool:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("UPDATE health_logs SET remediated = 1 WHERE id = ?;", (log_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def clear(self) -> int:
        conn = self.db.get_connection()
        try:
            cursor = conn.execute("DELETE FROM health_logs;")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
