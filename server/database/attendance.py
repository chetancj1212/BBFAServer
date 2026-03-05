import sqlite3
import logging
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AttendanceDatabaseManager:
    """SQLite-based attendance database manager"""

    # Column whitelists for dynamic update queries (Fix #10)
    _GROUP_COLUMNS = frozenset({
        "name", "description", "is_active", "room_id",
        "late_threshold_minutes", "late_threshold_enabled", "class_start_time",
    })
    _MEMBER_COLUMNS = frozenset({"name", "enrollment_no", "group_id", "is_active"})

    def __init__(self, database_path: str):
        """
        Initialize the attendance database manager

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = Path(database_path)
        # Scalability Fix #4: replaced threading.Lock with nullcontext.
        # SQLite WAL mode + busy_timeout handles concurrency natively.
        self.lock = nullcontext()

        # Ensure directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Run PRAGMAs once — WAL mode persists per-file (Fix #12)
        self._configure_pragmas()

        # Initialize database
        self._initialize_database()

    def _configure_pragmas(self):
        """Set database-level PRAGMAs once (WAL persists across connections)."""
        conn = sqlite3.connect(self.database_path, timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.commit()
        finally:
            conn.close()

    def _initialize_database(self):
        """Initialize the database schema"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create attendance_groups table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_groups (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        late_threshold_minutes INTEGER,
                        late_threshold_enabled BOOLEAN DEFAULT 0,
                        class_start_time TEXT DEFAULT '08:00',
                        room_id TEXT
                    )
                """
                )

                # Migration: add room_id column if it doesn't exist yet
                cursor.execute("PRAGMA table_info(attendance_groups)")
                columns = [col[1] for col in cursor.fetchall()]
                if "room_id" not in columns:
                    cursor.execute(
                        "ALTER TABLE attendance_groups ADD COLUMN room_id TEXT"
                    )
                    logger.info("[AttendanceDB] Added room_id column to attendance_groups")

                # Create attendance_members table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_members (
                        person_id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        enrollment_no TEXT,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (group_id) REFERENCES attendance_groups (id)
                    )
                """
                )

                # Create attendance_records table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_records (
                        id TEXT PRIMARY KEY,
                        person_id TEXT NOT NULL,
                        group_id TEXT NOT NULL,
                        timestamp TIMESTAMP NOT NULL,
                        confidence REAL NOT NULL,
                        location TEXT,
                        notes TEXT,
                        is_manual BOOLEAN DEFAULT 0,
                        created_by TEXT,
                        FOREIGN KEY (person_id) REFERENCES attendance_members (person_id),
                        FOREIGN KEY (group_id) REFERENCES attendance_groups (id)
                    )
                """
                )

                # Create attendance_sessions table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_sessions (
                        id TEXT PRIMARY KEY,
                        person_id TEXT NOT NULL,
                        group_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        check_in_time TIMESTAMP,
                        total_hours REAL,
                        status TEXT NOT NULL DEFAULT 'absent',
                        is_late BOOLEAN DEFAULT 0,
                        late_minutes INTEGER,
                        notes TEXT,
                        FOREIGN KEY (person_id) REFERENCES attendance_members (person_id),
                        FOREIGN KEY (group_id) REFERENCES attendance_groups (id)
                    )
                """
                )

                # Create attendance_settings table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_settings (
                        id INTEGER PRIMARY KEY CHECK (id = 1),
                        late_threshold_minutes INTEGER DEFAULT 15,
                        enable_location_tracking BOOLEAN DEFAULT 0,
                        confidence_threshold REAL DEFAULT 0.7,
                        attendance_cooldown_seconds INTEGER DEFAULT 10,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )

                # Migration: Add attendance_cooldown_seconds column if it doesn't exist
                try:
                    cursor.execute(
                        "ALTER TABLE attendance_settings ADD COLUMN attendance_cooldown_seconds INTEGER DEFAULT 10"
                    )
                except sqlite3.OperationalError:
                    # Column already exists, ignore the error
                    pass

                # Migration: Add class_start_time column if it doesn't exist
                try:
                    cursor.execute(
                        "ALTER TABLE attendance_groups ADD COLUMN class_start_time TEXT DEFAULT '08:00'"
                    )
                except sqlite3.OperationalError:
                    # Column already exists, ignore the error
                    pass

                # Migration: Add check_in_time column to attendance_sessions if it doesn't exist
                try:
                    cursor.execute(
                        "ALTER TABLE attendance_sessions ADD COLUMN check_in_time TIMESTAMP"
                    )
                except sqlite3.OperationalError:
                    # Column already exists, ignore the error
                    pass

                # Migration: Add late_threshold_enabled column if it doesn't exist
                try:
                    cursor.execute(
                        "ALTER TABLE attendance_groups ADD COLUMN late_threshold_enabled BOOLEAN DEFAULT 0"
                    )
                except sqlite3.OperationalError:
                    # Column already exists, ignore the error
                    pass

                # Migration: Add enrollment_no column to attendance_members if it doesn't exist
                try:
                    cursor.execute(
                        "ALTER TABLE attendance_members ADD COLUMN enrollment_no TEXT"
                    )
                except sqlite3.OperationalError:
                    # Column already exists, ignore the error
                    pass

                # Create attendance_subjects table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_subjects (
                        id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (group_id) REFERENCES attendance_groups (id)
                    )
                    """
                )

                # Create attendance_subject_members table (Phase 3.1)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS attendance_subject_members (
                        person_id TEXT NOT NULL,
                        subject_id TEXT NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (person_id, subject_id),
                        FOREIGN KEY (person_id) REFERENCES attendance_members (person_id),
                        FOREIGN KEY (subject_id) REFERENCES attendance_subjects (id)
                    )
                    """
                )

                # Create indexes for better performance
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_members_group_id ON attendance_members(group_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_records_person_id ON attendance_records(person_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_records_group_id ON attendance_records(group_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_records_timestamp ON attendance_records(timestamp)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_person_id ON attendance_sessions(person_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_group_id ON attendance_sessions(group_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_date ON attendance_sessions(date)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_subjects_group_id ON attendance_subjects(group_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_subject_members_subject_id ON attendance_subject_members(subject_id)"
                )

                # Create rooms table (migrated from JSON files)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS rooms (
                        id TEXT PRIMARY KEY,
                        room_no TEXT NOT NULL UNIQUE,
                        device_name TEXT NOT NULL,
                        description TEXT DEFAULT ''
                    )
                    """
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_rooms_device_name ON rooms(device_name)"
                )

                # Insert default settings if not exists
                cursor.execute(
                    "INSERT OR IGNORE INTO attendance_settings (id) VALUES (1)"
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to initialize attendance database: {e}")
            raise

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(
                self.database_path, timeout=30.0, check_same_thread=False
            )
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    # Group Management Methods
    def create_group(self, group_data: Dict[str, Any]) -> bool:
        """Create a new attendance group"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        INSERT INTO attendance_groups 
                        (id, name, description, late_threshold_minutes, late_threshold_enabled)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (
                            group_data["id"],
                            group_data["name"],
                            group_data.get("description"),
                            group_data.get("settings", {}).get(
                                "late_threshold_minutes"
                            ),
                            group_data.get("settings", {}).get(
                                "late_threshold_enabled", False
                            ),
                        ),
                    )

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to create group: {e}")
            return False

    def get_groups(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all attendance groups"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM attendance_groups"
                if active_only:
                    query += " WHERE is_active = 1"
                query += " ORDER BY name"

                cursor.execute(query)

                groups = []
                for row in cursor.fetchall():
                    group = dict(row)
                    
                    # Fetch member count
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM attendance_members WHERE group_id = ? AND is_active = 1",
                        (group["id"],),
                    )
                    group["member_count"] = cursor.fetchone()["count"]

                    group["settings"] = {
                        "late_threshold_minutes": group.pop(
                            "late_threshold_minutes", 15
                        ),
                        "late_threshold_enabled": bool(
                            group.pop("late_threshold_enabled", False)
                        ),
                        "class_start_time": group.pop("class_start_time", "08:00"),
                    }
                    groups.append(group)

                return groups

        except Exception as e:
            logger.error(f"Failed to get groups: {e}")
            return []

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific attendance group"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM attendance_groups WHERE id = ?", (group_id,)
                )
                row = cursor.fetchone()

                if row:
                    group = dict(row)
                    group["settings"] = {
                        "late_threshold_minutes": group.pop(
                            "late_threshold_minutes", 15
                        ),
                        "late_threshold_enabled": bool(
                            group.pop("late_threshold_enabled", False)
                        ),
                        "class_start_time": group.pop("class_start_time", "08:00"),
                    }
                    return group
                return None

        except Exception as e:
            logger.error(f"Failed to get group {group_id}: {e}")
            return None

    def update_group(self, group_id: str, updates: Dict[str, Any]) -> bool:
        """Update an attendance group"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Build dynamic update query with column whitelisting
                    set_clauses = []
                    values = []

                    for key, value in updates.items():
                        if key == "settings":
                            for setting_key, setting_value in value.items():
                                if setting_key not in self._GROUP_COLUMNS:
                                    logger.warning(f"Rejected invalid column: {setting_key}")
                                    continue
                                set_clauses.append(f"{setting_key} = ?")
                                values.append(setting_value)
                        else:
                            if key not in self._GROUP_COLUMNS:
                                logger.warning(f"Rejected invalid column: {key}")
                                continue
                            set_clauses.append(f"{key} = ?")
                            values.append(value)

                    if not set_clauses:
                        return True

                    values.append(group_id)
                    query = f"UPDATE attendance_groups SET {', '.join(set_clauses)} WHERE id = ?"

                    cursor.execute(query, values)
                    conn.commit()

                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update group {group_id}: {e}")
            return False

    def delete_group(self, group_id: str) -> bool:
        """Soft delete an attendance group"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        "UPDATE attendance_groups SET is_active = 0 WHERE id = ?",
                        (group_id,),
                    )

                    conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete group {group_id}: {e}")
            return False

    # Member Management Methods
    def add_member(self, member_data: Dict[str, Any]) -> bool:
        """Add a new attendance member"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO attendance_members 
                        (person_id, group_id, name, enrollment_no)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            member_data["person_id"],
                            member_data["group_id"],
                            member_data["name"],
                            member_data.get("enrollment_no"),
                        ),
                    )

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to add member: {e}")
            return False

    def get_member(self, person_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific attendance member"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM attendance_members WHERE person_id = ? AND is_active = 1",
                    (person_id,),
                )

                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get member {person_id}: {e}")
            return None

    def get_members(self) -> List[Dict[str, Any]]:
        """Get all active attendance members across all groups"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM attendance_members WHERE is_active = 1 ORDER BY name"
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get all members: {e}")
            return []

    def get_group_members(self, group_id: str) -> List[Dict[str, Any]]:
        """Get all members of a specific group"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM attendance_members WHERE group_id = ? AND is_active = 1 ORDER BY name",
                    (group_id,),
                )

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get group members for {group_id}: {e}")
            return []

    def get_group_person_ids(self, group_id: str) -> List[str]:
        """Get all person_ids for a specific group (for recognition filtering)"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT person_id FROM attendance_members WHERE group_id = ? AND is_active = 1",
                    (group_id,),
                )

                return [row["person_id"] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get person_ids for group {group_id}: {e}")
            return []

    def update_member(self, person_id: str, updates: Dict[str, Any]) -> bool:
        """Update an attendance member"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Build dynamic update query with column whitelisting
                    set_clauses = []
                    values = []

                    for key, value in updates.items():
                        if key not in self._MEMBER_COLUMNS:
                            logger.warning(f"Rejected invalid member column: {key}")
                            continue
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                    if not set_clauses:
                        return True

                    values.append(person_id)
                    query = f"UPDATE attendance_members SET {', '.join(set_clauses)} WHERE person_id = ?"

                    cursor.execute(query, values)
                    conn.commit()

                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update member {person_id}: {e}")
            return False

    def remove_member(self, person_id: str) -> bool:
        """Soft delete an attendance member"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        "UPDATE attendance_members SET is_active = 0 WHERE person_id = ?",
                        (person_id,),
                    )

                    conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to remove member {person_id}: {e}")
            return False

    # Record Management Methods
    def add_record(self, record_data: Dict[str, Any]) -> bool:
        """Add a new attendance record"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        INSERT INTO attendance_records 
                        (id, person_id, group_id, timestamp, confidence, 
                         location, notes, is_manual, created_by)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            record_data["id"],
                            record_data["person_id"],
                            record_data["group_id"],
                            record_data["timestamp"],
                            record_data["confidence"],
                            record_data.get("location"),
                            record_data.get("notes"),
                            record_data.get("is_manual", False),
                            record_data.get("created_by"),
                        ),
                    )

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to add record: {e}")
            return False

    def get_records(
        self,
        group_id: Optional[str] = None,
        person_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get attendance records with optional filters"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM attendance_records WHERE 1=1"
                params = []

                if group_id:
                    query += " AND group_id = ?"
                    params.append(group_id)

                if person_id:
                    query += " AND person_id = ?"
                    params.append(person_id)

                if start_date:
                    query += " AND timestamp >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND timestamp <= ?"
                    params.append(end_date)

                query += " ORDER BY timestamp DESC"

                if limit:
                    query += " LIMIT ?"
                    params.append(limit)

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get records: {e}")
            return []

    # Session Management Methods
    def upsert_session(self, session_data: Dict[str, Any]) -> bool:
        """Insert or update an attendance session"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO attendance_sessions 
                        (id, person_id, group_id, date, check_in_time, total_hours,
                         status, is_late, late_minutes, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            session_data["id"],
                            session_data["person_id"],
                            session_data["group_id"],
                            session_data["date"],
                            session_data.get("check_in_time"),
                            session_data.get("total_hours"),
                            session_data["status"],
                            session_data.get("is_late", False),
                            session_data.get("late_minutes"),
                            session_data.get("notes"),
                        ),
                    )

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to upsert session: {e}")
            return False

    def get_session(self, person_id: str, date: str) -> Optional[Dict[str, Any]]:
        """Get a specific attendance session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT * FROM attendance_sessions WHERE person_id = ? AND date = ?",
                    (person_id, date),
                )

                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get session for {person_id} on {date}: {e}")
            return None

    def get_sessions(
        self,
        group_id: Optional[str] = None,
        person_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get attendance sessions with optional filters"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM attendance_sessions WHERE 1=1"
                params = []

                if group_id:
                    query += " AND group_id = ?"
                    params.append(group_id)

                if person_id:
                    query += " AND person_id = ?"
                    params.append(person_id)

                if start_date:
                    query += " AND date >= ?"
                    params.append(start_date)

                if end_date:
                    query += " AND date <= ?"
                    params.append(end_date)

                query += " ORDER BY date DESC, person_id"

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get sessions: {e}")
            return []

    # Settings Management Methods
    def get_settings(self) -> Dict[str, Any]:
        """Get attendance settings"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT * FROM attendance_settings WHERE id = 1")
                row = cursor.fetchone()

                if row:
                    settings = dict(row)
                    settings.pop("id", None)
                    settings.pop("updated_at", None)
                    return settings

                # Return default settings if none found
                return {
                    "late_threshold_minutes": 15,
                    "enable_location_tracking": False,
                    "confidence_threshold": 0.7,
                    "attendance_cooldown_seconds": 10,
                }

        except Exception as e:
            logger.error(f"Failed to get settings: {e}")
            return {}

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """Update attendance settings"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Build dynamic update query
                    set_clauses = []
                    values = []

                    for key, value in settings.items():
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                    if not set_clauses:
                        return True

                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    query = f"UPDATE attendance_settings SET {', '.join(set_clauses)} WHERE id = 1"

                    cursor.execute(query, values)
                    conn.commit()

                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to update settings: {e}")
            return False

    # Utility Methods
    def cleanup_old_data(self, days_to_keep: int = 90) -> bool:
        """Clean up old records and sessions"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Calculate cutoff date
                    cutoff_date = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    cutoff_date = cutoff_date.replace(
                        day=cutoff_date.day - days_to_keep
                    )

                    # Delete old records
                    cursor.execute(
                        "DELETE FROM attendance_records WHERE timestamp < ?",
                        (cutoff_date,),
                    )

                    # Delete old sessions
                    cutoff_date_str = cutoff_date.strftime("%Y-%m-%d")
                    cursor.execute(
                        "DELETE FROM attendance_sessions WHERE date < ?",
                        (cutoff_date_str,),
                    )

                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get counts
                cursor.execute(
                    "SELECT COUNT(*) as count FROM attendance_groups WHERE is_active = 1"
                )
                groups_count = cursor.fetchone()["count"]

                cursor.execute(
                    "SELECT COUNT(*) as count FROM attendance_members WHERE is_active = 1"
                )
                members_count = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM attendance_records")
                records_count = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM attendance_sessions")
                sessions_count = cursor.fetchone()["count"]

                # Phase 3.1: Add subject members count
                cursor.execute("SELECT COUNT(*) as count FROM attendance_subject_members")
                subject_members_count = cursor.fetchone()["count"]

                # Get database file size
                db_size = (
                    self.database_path.stat().st_size
                    if self.database_path.exists()
                    else 0
                )

                return {
                    "total_groups": groups_count,
                    "total_members": members_count,
                    "total_records": records_count,
                    "total_sessions": sessions_count,
                    "total_subject_members": subject_members_count,
                    "database_path": str(self.database_path),
                    "database_size_bytes": db_size,
                    "database_size_mb": round(db_size / (1024 * 1024), 2),
                }

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

    # Subject-Member Management (Phase 3.1)
    def assign_student_to_subject(self, person_id: str, subject_id: str) -> bool:
        """Assign a student to a specific subject"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT OR IGNORE INTO attendance_subject_members (person_id, subject_id) VALUES (?, ?)",
                        (person_id, subject_id),
                    )
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Failed to assign student {person_id} to subject {subject_id}: {e}")
            return False

    def remove_student_from_subject(self, person_id: str, subject_id: str) -> bool:
        """Remove a student from a specific subject"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM attendance_subject_members WHERE person_id = ? AND subject_id = ?",
                        (person_id, subject_id),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to remove student {person_id} from subject {subject_id}: {e}")
            return False

    def get_subject_members(self, subject_id: str) -> List[Dict[str, Any]]:
        """Get all students enrolled in a specific subject"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT m.* FROM attendance_members m
                    INNER JOIN attendance_subject_members sm ON m.person_id = sm.person_id
                    WHERE sm.subject_id = ? AND m.is_active = 1
                    ORDER BY m.name
                    """,
                    (subject_id,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get members for subject {subject_id}: {e}")
            return []

    def get_student_subjects(self, person_id: str) -> List[Dict[str, Any]]:
        """Get all subjects a student is enrolled in"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT s.* FROM attendance_subjects s
                    INNER JOIN attendance_subject_members sm ON s.id = sm.subject_id
                    WHERE sm.person_id = ?
                    ORDER BY s.name
                    """,
                    (person_id,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get subjects for student {person_id}: {e}")
            return []

    def get_group_attendance_for_archive(self, group_id: str) -> List[Dict[str, Any]]:
        """
        Get all members with their current session attendance status for archiving.
        
        Args:
            group_id: Group identifier
            
        Returns:
            List of member records with attendance status
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                today = datetime.now().strftime("%Y-%m-%d")

                # Get all members with their session data for today
                cursor.execute(
                    """
                    SELECT 
                        m.person_id,
                        m.name,
                        m.enrollment_no,
                        s.status,
                        s.check_in_time,
                        s.is_late,
                        s.late_minutes,
                        s.notes
                    FROM attendance_members m
                    LEFT JOIN attendance_sessions s 
                        ON m.person_id = s.person_id 
                        AND s.group_id = ? 
                        AND s.date = ?
                    WHERE m.group_id = ? AND m.is_active = 1
                    ORDER BY m.name
                    """,
                    (group_id, today, group_id),
                )

                records = []
                for row in cursor.fetchall():
                    records.append({
                        "person_id": row["person_id"],
                        "name": row["name"],
                        "enrollment_no": row["enrollment_no"],
                        "status": row["status"] or "absent",
                        "check_in_time": row["check_in_time"],
                        "is_late": bool(row["is_late"]) if row["is_late"] is not None else False,
                        "late_minutes": row["late_minutes"] or 0,
                        "notes": row["notes"],
                    })

                return records

        except Exception as e:
            logger.error(f"Failed to get group attendance for archive {group_id}: {e}")
            return []

    def clear_group_session_data(self, group_id: str) -> bool:
        """
        Clear all session and record data for a group (reset for new session).
        This preserves members but removes attendance records and sessions.
        
        Args:
            group_id: Group identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Delete attendance records for this group
                    cursor.execute(
                        "DELETE FROM attendance_records WHERE group_id = ?",
                        (group_id,),
                    )
                    records_deleted = cursor.rowcount

                    # Delete attendance sessions for this group
                    cursor.execute(
                        "DELETE FROM attendance_sessions WHERE group_id = ?",
                        (group_id,),
                    )
                    sessions_deleted = cursor.rowcount

                    conn.commit()
                    logger.info(
                        f"Cleared group {group_id}: {records_deleted} records, {sessions_deleted} sessions"
                    )
                    return True

        except Exception as e:
            logger.error(f"Failed to clear group session data {group_id}: {e}")
            return False

    # ── Subject CRUD ──

    def add_subject(self, subject_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a subject to a group"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO attendance_subjects (id, group_id, name) VALUES (?, ?, ?)",
                        (subject_data["id"], subject_data["group_id"], subject_data["name"]),
                    )
                    conn.commit()
                    return subject_data
        except Exception as e:
            logger.error(f"Failed to add subject: {e}")
            return None

    def get_subjects(self, group_id: str) -> List[Dict[str, Any]]:
        """Get all subjects for a group"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, group_id, name, created_at FROM attendance_subjects WHERE group_id = ? ORDER BY name",
                    (group_id,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get subjects: {e}")
            return []

    def delete_subject(self, subject_id: str) -> bool:
        """Delete a subject"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM attendance_subjects WHERE id = ?", (subject_id,))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete subject: {e}")
            return False

    # ── Cross-group member search ──

    def search_all_members(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search all active members across all groups by name or enrollment number"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                search = f"%{query}%"
                cursor.execute(
                    """
                    SELECT m.person_id, m.name, m.enrollment_no, m.group_id, g.name as group_name
                    FROM attendance_members m
                    LEFT JOIN attendance_groups g ON m.group_id = g.id
                    WHERE m.is_active = 1
                      AND (m.name LIKE ? OR m.enrollment_no LIKE ?)
                    ORDER BY m.name
                    LIMIT ?
                    """,
                    (search, search, limit),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to search members: {e}")
            return []

    def assign_member_to_group(self, person_id: str, new_group_id: str) -> bool:
        """Move a member to a different group"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE attendance_members SET group_id = ? WHERE person_id = ? AND is_active = 1",
                        (new_group_id, person_id),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to assign member: {e}")
            return False

    # ── Room CRUD (migrated from JSON) ──

    def get_rooms(self) -> List[Dict[str, Any]]:
        """Get all rooms"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM rooms ORDER BY room_no")
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get rooms: {e}")
            return []

    def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific room by ID"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM rooms WHERE id = ?", (room_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get room {room_id}: {e}")
            return None

    def get_room_by_device_name(self, device_name: str) -> Optional[Dict[str, Any]]:
        """Get a room by its ESP device name"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM rooms WHERE device_name = ?", (device_name,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get room by device {device_name}: {e}")
            return None

    def create_room(self, room_data: Dict[str, Any]) -> bool:
        """Create a new room"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO rooms (id, room_no, device_name, description) VALUES (?, ?, ?, ?)",
                        (
                            room_data["id"],
                            room_data["room_no"],
                            room_data["device_name"],
                            room_data.get("description", ""),
                        ),
                    )
                    conn.commit()
                    return True
        except sqlite3.IntegrityError:
            logger.warning(f"Room already exists: {room_data.get('room_no')}")
            return False
        except Exception as e:
            logger.error(f"Failed to create room: {e}")
            return False

    def delete_room(self, room_id: str) -> bool:
        """Delete a room by ID"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete room {room_id}: {e}")
            return False

    def vacuum(self) -> bool:
        """Optimize database storage"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    conn.execute("VACUUM")
                    return True
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False

    def factory_reset(self) -> bool:
        """Wipe all attendance and group data (DANGEROUS)"""
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM attendance_records")
                    cursor.execute("DELETE FROM attendance_sessions")
                    cursor.execute("DELETE FROM attendance_members")
                    cursor.execute("DELETE FROM attendance_groups")
                    cursor.execute("DELETE FROM attendance_subject_members")
                    cursor.execute("DELETE FROM attendance_subjects")
                    conn.commit()
                    return True
        except Exception as e:
            logger.error(f"Failed to factory reset: {e}")
            return False

    def close(self):
        """Close the database connection"""

    def __del__(self):
        """Destructor to ensure proper cleanup"""
        self.close()
