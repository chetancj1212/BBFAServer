"""
FastAPI dependency functions for accessing application state.
Replaces module-level globals with proper request-scoped DI via app.state.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from fastapi import Request, HTTPException

from database.attendance import AttendanceDatabaseManager
from database.face import FaceDatabaseManager
from database.history import AttendanceHistoryManager

logger = logging.getLogger(__name__)


def get_attendance_db(request: Request) -> AttendanceDatabaseManager:
    """Get attendance database manager from app state."""
    db = getattr(request.app.state, "attendance_db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Attendance database not initialized")
    return db


def get_face_db(request: Request) -> FaceDatabaseManager:
    """Get face database manager from app state."""
    db = getattr(request.app.state, "face_db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Face database not initialized")
    return db


def get_history_db(request: Request) -> AttendanceHistoryManager:
    """Get history database manager from app state."""
    db = getattr(request.app.state, "history_db", None)
    if db is None:
        raise HTTPException(status_code=503, detail="History database not initialized")
    return db


def get_face_detector(request: Request):
    """Get face detector model from app state."""
    return getattr(request.app.state, "face_detector", None)


def get_face_recognizer(request: Request):
    """Get face recognizer model from app state."""
    return getattr(request.app.state, "face_recognizer", None)


def get_liveness_detector(request: Request):
    """Get liveness detector model from app state."""
    return getattr(request.app.state, "liveness_detector", None)


def get_inference_semaphore(request: Request) -> asyncio.Semaphore:
    """Get inference concurrency semaphore from app state."""
    sem = getattr(request.app.state, "inference_semaphore", None)
    if sem is None:
        # Fallback: create an unbounded semaphore (no limiting)
        return asyncio.Semaphore(100)
    return sem


def get_thread_pool(request: Request) -> ThreadPoolExecutor:
    """Get the AI inference thread pool from app state."""
    pool = getattr(request.app.state, "thread_pool", None)
    # Fallback: use default executor (None = asyncio default)
    return pool

