"""
SQLite Database Manager for Attendance History

This module provides a SQLite-based database manager for storing
historical attendance data when sessions are reset.
"""

import sqlite3
import logging
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AttendanceHistoryManager:
    """SQLite-based attendance history database manager"""

    def __init__(self, database_path: str):
        """
        Initialize the history database manager

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = Path(database_path)
        # Scalability Fix #4: replaced threading.Lock with nullcontext.
        # SQLite WAL mode + busy_timeout handles concurrency natively.
        self.lock = nullcontext()

        # Ensure directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._initialize_database()

    def _initialize_database(self):
        """Initialize the database schema"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create history_sessions table - stores session metadata
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history_sessions (
                        id TEXT PRIMARY KEY,
                        group_id TEXT NOT NULL,
                        group_name TEXT,
                        session_name TEXT,
                        started_at TIMESTAMP,
                        ended_at TIMESTAMP,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        total_members INTEGER DEFAULT 0,
                        present_count INTEGER DEFAULT 0,
                        absent_count INTEGER DEFAULT 0,
                        late_count INTEGER DEFAULT 0
                    )
                """
                )

                # Migration: Add subject_name column if it doesn't exist
                try:
                    cursor.execute(
                        "ALTER TABLE history_sessions ADD COLUMN subject_name TEXT"
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists

                # Create history_attendance table - stores individual attendance records
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS history_attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        person_id TEXT NOT NULL,
                        person_name TEXT,
                        enrollment_no TEXT,
                        group_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'absent',
                        check_in_time TIMESTAMP,
                        is_late BOOLEAN DEFAULT 0,
                        late_minutes INTEGER DEFAULT 0,
                        confidence REAL,
                        notes TEXT,
                        FOREIGN KEY (session_id) REFERENCES history_sessions(id)
                    )
                """
                )

                # Create indexes for better performance
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_sessions_group ON history_sessions(group_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_sessions_date ON history_sessions(started_at)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_attendance_session ON history_attendance(session_id)"
                )
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_history_attendance_person ON history_attendance(person_id)"
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to initialize history database: {e}")
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
            # Enable WAL mode for concurrent reads during writes (handles 30+ concurrent users)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout for busy DB
            conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe with WAL
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def archive_session(
        self,
        session_id: str,
        group_id: str,
        group_name: str,
        session_name: str,
        started_at: Optional[str],
        ended_at: Optional[str],
        attendance_records: List[Dict[str, Any]],
        subject_name: Optional[str] = None,
    ) -> bool:
        """
        Archive a complete session with all attendance records.

        Args:
            session_id: Unique session identifier
            group_id: Group/class identifier
            group_name: Name of the group/class
            session_name: Name of the session
            started_at: Session start time
            ended_at: Session end time
            attendance_records: List of attendance records for this session

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Calculate stats
                    total_members = len(attendance_records)
                    present_count = sum(1 for r in attendance_records if r.get("status") == "present")
                    late_count = sum(1 for r in attendance_records if r.get("is_late"))
                    absent_count = total_members - present_count

                    # Insert session record
                    cursor.execute(
                        """
                        INSERT INTO history_sessions 
                        (id, group_id, group_name, session_name, subject_name, started_at, ended_at,
                         total_members, present_count, absent_count, late_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session_id,
                            group_id,
                            group_name,
                            session_name,
                            subject_name,
                            started_at,
                            ended_at,
                            total_members,
                            present_count,
                            absent_count,
                            late_count,
                        ),
                    )

                    # Insert attendance records
                    for record in attendance_records:
                        cursor.execute(
                            """
                            INSERT INTO history_attendance 
                            (session_id, person_id, person_name, enrollment_no, group_id,
                             status, check_in_time, is_late, late_minutes, confidence, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                session_id,
                                record.get("person_id"),
                                record.get("name"),
                                record.get("enrollment_no"),
                                group_id,
                                record.get("status", "absent"),
                                record.get("check_in_time"),
                                record.get("is_late", False),
                                record.get("late_minutes", 0),
                                record.get("confidence"),
                                record.get("notes"),
                            ),
                        )

                    conn.commit()
                    logger.info(
                        f"Archived session {session_id}: {present_count}/{total_members} present"
                    )
                    return True

        except Exception as e:
            logger.error(f"Failed to archive session {session_id}: {e}")
            return False

    def get_session_history(
        self,
        group_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get session history with optional filtering.

        Args:
            group_id: Filter by group ID (optional)
            limit: Maximum number of records to return
            offset: Offset for pagination

        Returns:
            List of session history records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = "SELECT * FROM history_sessions WHERE 1=1"
                params = []

                if group_id:
                    query += " AND group_id = ?"
                    params.append(group_id)

                query += " ORDER BY archived_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    def get_session_attendance(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get attendance records for a specific archived session.

        Args:
            session_id: Session identifier

        Returns:
            List of attendance records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT * FROM history_attendance 
                    WHERE session_id = ? 
                    ORDER BY person_name
                    """,
                    (session_id,),
                )
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get session attendance for {session_id}: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its attendance records from history.

        Args:
            session_id: Session identifier to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Check if session exists
                    cursor.execute(
                        "SELECT id FROM history_sessions WHERE id = ?",
                        (session_id,)
                    )
                    if not cursor.fetchone():
                        return False

                    # Delete attendance records first (foreign key reference)
                    cursor.execute(
                        "DELETE FROM history_attendance WHERE session_id = ?",
                        (session_id,)
                    )

                    # Delete session
                    cursor.execute(
                        "DELETE FROM history_sessions WHERE id = ?",
                        (session_id,)
                    )

                    conn.commit()
                    logger.info(f"Deleted session {session_id} from history")
                    return True

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def get_student_history(
        self,
        person_id: str,
        group_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get attendance history for a specific student.

        Args:
            person_id: Student/person identifier
            group_id: Filter by group ID (optional)
            limit: Maximum number of records to return

        Returns:
            List of attendance records with session info
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT 
                        ha.*,
                        hs.session_name,
                        hs.started_at as session_started_at,
                        hs.ended_at as session_ended_at,
                        hs.group_name
                    FROM history_attendance ha
                    JOIN history_sessions hs ON ha.session_id = hs.id
                    WHERE ha.person_id = ?
                """
                params: List[Any] = [person_id]

                if group_id:
                    query += " AND ha.group_id = ?"
                    params.append(group_id)

                query += " ORDER BY hs.started_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get student history for {person_id}: {e}")
            return []

    def get_group_statistics(self, group_id: str) -> Dict[str, Any]:
        """
        Get aggregate statistics for a group.

        Args:
            group_id: Group identifier

        Returns:
            Dictionary with aggregate statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get session count and averages
                cursor.execute(
                    """
                    SELECT 
                        COUNT(*) as total_sessions,
                        AVG(present_count * 100.0 / NULLIF(total_members, 0)) as avg_attendance_rate,
                        SUM(present_count) as total_present,
                        SUM(absent_count) as total_absent,
                        SUM(late_count) as total_late
                    FROM history_sessions
                    WHERE group_id = ?
                    """,
                    (group_id,),
                )
                row = cursor.fetchone()

                return {
                    "group_id": group_id,
                    "total_sessions": row["total_sessions"] or 0,
                    "avg_attendance_rate": round(row["avg_attendance_rate"] or 0, 2),
                    "total_present": row["total_present"] or 0,
                    "total_absent": row["total_absent"] or 0,
                    "total_late": row["total_late"] or 0,
                }

        except Exception as e:
            logger.error(f"Failed to get group statistics for {group_id}: {e}")
            return {
                "group_id": group_id,
                "total_sessions": 0,
                "avg_attendance_rate": 0,
                "total_present": 0,
                "total_absent": 0,
                "total_late": 0,
            }

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its attendance records from history.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()

                    # Delete attendance records first
                    cursor.execute(
                        "DELETE FROM history_attendance WHERE session_id = ?",
                        (session_id,),
                    )

                    # Delete session record
                    cursor.execute(
                        "DELETE FROM history_sessions WHERE id = ?",
                        (session_id,),
                    )

                    conn.commit()
                    return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with database statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) as total FROM history_sessions")
                total_sessions = cursor.fetchone()["total"]

                cursor.execute("SELECT COUNT(*) as total FROM history_attendance")
                total_records = cursor.fetchone()["total"]

                db_size = (
                    self.database_path.stat().st_size
                    if self.database_path.exists()
                    else 0
                )

                return {
                    "total_sessions": total_sessions,
                    "total_records": total_records,
                    "database_path": str(self.database_path),
                    "database_size_bytes": db_size,
                    "database_size_mb": round(db_size / (1024 * 1024), 2),
                }

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {
                "total_sessions": 0,
                "total_records": 0,
                "database_path": str(self.database_path),
                "database_size_bytes": 0,
                "database_size_mb": 0,
            }

    def update_attendance_status(
        self,
        session_id: str,
        person_id: str,
        status: str,
        is_late: bool = False,
        late_minutes: int = 0,
        notes: str = None
    ) -> bool:
        """
        Update attendance status for a specific record in history.
        
        Args:
            session_id: Session identifier
            person_id: Person identifier
            status: New status (present, absent, etc.)
            is_late: Whether the person was late
            late_minutes: Minutes late
            notes: Optional notes
            
        Returns:
            bool: True if successful
        """
        try:
            with self.lock:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Check if record exists
                    cursor.execute(
                        "SELECT id FROM history_attendance WHERE session_id = ? AND person_id = ?",
                        (session_id, person_id)
                    )
                    row = cursor.fetchone()
                    
                    if row:
                        # Update existing
                        query = """
                            UPDATE history_attendance 
                            SET status = ?, is_late = ?, late_minutes = ?, notes = COALESCE(?, notes)
                            WHERE session_id = ? AND person_id = ?
                        """
                        params = (status, is_late, late_minutes, notes, session_id, person_id)
                        cursor.execute(query, params)
                    else:
                        # Record doesn't exist (maybe they were not in the group roster at the time?)
                        # We should probably get group_id from session
                        cursor.execute("SELECT group_id FROM history_sessions WHERE id = ?", (session_id,))
                        session = cursor.fetchone()
                        if not session:
                            return False
                            
                        # Insert new record
                        query = """
                            INSERT INTO history_attendance 
                            (session_id, person_id, person_name, group_id, status, is_late, late_minutes, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """
                        # We don't have name/enrollment if inserting fresh, so this is tricky.
                        # Ideally frontend should provide this, but for now let's assume update only works for existing rows
                        # OR we assume the caller ensures this person "should" be there.
                        # For simplicity, let's ONLY support updating existing records for now.
                        logger.warning(f"Attempted to update non-existent history record for {person_id} in {session_id}")
                        return False

                    # Now we need to update session stats (present_count, etc)
                    # Recalculate stats for this session
                    cursor.execute(
                        """
                        SELECT 
                            count(*) as total,
                            sum(case when status = 'present' then 1 else 0 end) as present,
                            sum(case when is_late = 1 then 1 else 0 end) as late
                        FROM history_attendance
                        WHERE session_id = ?
                        """,
                        (session_id,)
                    )
                    stats = cursor.fetchone()
                    
                    total = stats['total']
                    present = stats['present'] or 0
                    late = stats['late'] or 0
                    absent = total - present # Absent is derived
                    
                    cursor.execute(
                        """
                        UPDATE history_sessions
                        SET present_count = ?, absent_count = ?, late_count = ?
                        WHERE id = ?
                        """,
                        (present, absent, late, session_id)
                    )
                    
                    conn.commit()
                    return True

        except Exception as e:
            logger.error(f"Failed to update history attendance: {e}")
            return False

