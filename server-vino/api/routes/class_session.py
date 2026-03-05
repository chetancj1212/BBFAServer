"""
Class Session Management Routes
Handles class session lifecycle: create, start, end
"""

import json
import logging
from datetime import datetime
from typing import Optional, List
import ulid

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from middleware.api_key import verify_api_key
from api.dependencies import get_attendance_db, get_history_db
from api.schemas import AttendanceUpdate
from database.attendance import AttendanceDatabaseManager
from database.history import AttendanceHistoryManager

logger = logging.getLogger(__name__)

# Public router (accessible by students)
router = APIRouter(prefix="/class", tags=["class"])

# Admin router (protected by API key)
admin_router = APIRouter(prefix="/class", tags=["class"], dependencies=[Depends(verify_api_key)])

# In-memory storage for active class sessions
# In production, this would be in a database/Redis
active_sessions: dict = {}


# Pydantic models
class ClassSessionCreate(BaseModel):
    group_id: str
    name: Optional[str] = None
    subject_id: Optional[str] = None


class ClassSessionResponse(BaseModel):
    id: str
    group_id: str
    name: Optional[str]
    status: str  # "waiting", "active", "ended"
    started_at: Optional[str]
    ended_at: Optional[str]
    created_at: str


class ClassStatusBroadcast(BaseModel):
    status: str
    sessionId: Optional[str]
    groupId: Optional[str]
    startedAt: Optional[str]
    message: Optional[str]


def generate_session_id() -> str:
    """Generate unique session ID"""
    return ulid.ulid()


async def broadcast_class_status(status_data: dict):
    """Broadcast class status (no-op, WebSocket removed)"""
    pass


def get_current_class_status() -> dict:
    """Get the current class status"""
    # Find any active session
    for session_id, session in active_sessions.items():
        if session["status"] == "active":
            return {
                "status": "active",
                "sessionId": session_id,
                "groupId": session["group_id"],
                "startedAt": session.get("started_at"),
                "enableLiveness": session.get("enable_liveness", True),
                "subjectName": session.get("subject_name"),
                "message": "Class is in session"
            }
        elif session["status"] == "waiting":
            return {
                "status": "waiting",
                "sessionId": session_id,
                "groupId": session["group_id"],
                "startedAt": None,
                "enableLiveness": session.get("enable_liveness", True),
                "subjectName": session.get("subject_name"),
                "message": "Waiting for class to start"
            }
    
    return {
        "status": "waiting",
        "sessionId": None,
        "groupId": None,
        "startedAt": None,
        "message": "No active class session"
    }


@router.get("/status")
async def get_class_status():
    """Get current class status (REST endpoint)"""
    return get_current_class_status()


@admin_router.get("/sessions")
async def list_sessions(db: AttendanceDatabaseManager = Depends(get_attendance_db)):
    """List all active/recent sessions"""
    sessions_list = []
    
    for sid, s in active_sessions.items():
        present_count = 0
        total_members = 0
        
        try:
            # Get total members
            members = db.get_group_members(s["group_id"])
            total_members = len(members)
            
            # Get present count (unique persons who have records since start)
            started_at_str = s.get("started_at")
            if started_at_str and s["status"] == "active":
                start_dt = datetime.fromisoformat(started_at_str)
                records = db.get_records(group_id=s["group_id"], start_date=start_dt)
                present_count = len(set(r["person_id"] for r in records))
        except Exception as e:
            logger.error(f"Error getting stats for session {sid}: {e}")
            
        sessions_list.append({
            "id": sid,
            "group_id": s["group_id"],
            "name": s.get("name"),
            "status": s["status"],
            "started_at": s.get("started_at"),
            "ended_at": s.get("ended_at"),
            "created_at": s["created_at"],
            "present_count": present_count,
            "total_members": total_members,
        })

    return {"sessions": sessions_list}


def get_active_session_for_group(group_id: str, subject_id: Optional[str] = None) -> Optional[str]:
    """Check if a group already has an active or waiting session for this subject (Phase 3.1)"""
    for session_id, session in active_sessions.items():
        if session["group_id"] == group_id and session["status"] in ["active", "waiting"]:
            # If both have no subject, or both have the same subject ID
            if session.get("subject_id") == subject_id:
                return session_id
    return None


@admin_router.post("/sessions", response_model=ClassSessionResponse)
async def create_session(
    data: ClassSessionCreate,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Create a new class session (waiting state)"""
    # Verify group exists
    group = db.get_group(data.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if group already has an active session for this specific subject
    existing_session = get_active_session_for_group(data.group_id, data.subject_id)
    if existing_session:
        error_msg = f"Group already has an active session for subject {data.subject_id}" if data.subject_id else f"Group already has an active general session"
        raise HTTPException(
            status_code=400, 
            detail=error_msg
        )
    
    # Resolve subject name if subject_id provided
    subject_name = None
    if data.subject_id:
        subjects = db.get_subjects(data.group_id)
        subject = next((s for s in subjects if s["id"] == data.subject_id), None)
        if subject:
            subject_name = subject["name"]
    
    session_id = generate_session_id()
    now = datetime.now().isoformat()
    
    session = {
        "group_id": data.group_id,
        "name": data.name or group.get("name", "Class Session"),
        "subject_id": data.subject_id,
        "subject_name": subject_name,
        "status": "waiting",
        "started_at": None,
        "ended_at": None,
        "created_at": now,
    }
    
    active_sessions[session_id] = session
    
    # Broadcast status update
    await broadcast_class_status({
        "status": "waiting",
        "sessionId": session_id,
        "groupId": data.group_id,
        "startedAt": None,
        "message": f"Session created for {session['name']}"
    })
    
    return ClassSessionResponse(
        id=session_id,
        **session
    )


@admin_router.post("/sessions/{session_id}/start")
async def start_session(
    session_id: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Start a class session (transition from waiting to active).
    Clears previous session data for a fresh start (data is NOT archived here - only on end)."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    if session["status"] == "active":
        raise HTTPException(status_code=400, detail="Session already active")
    
    if session["status"] == "ended":
        raise HTTPException(status_code=400, detail="Session already ended")
    
    group_id = session["group_id"]
    
    # Clear current session data for fresh start (don't archive - that happens on end)
    db.clear_group_session_data(group_id)
    logger.info(f"[Class] Reset attendance data for group {group_id}")
    
    # Update session
    now = datetime.now().isoformat()
    session["status"] = "active"
    session["started_at"] = now
    
    # Broadcast status update
    await broadcast_class_status({
        "status": "active",
        "sessionId": session_id,
        "groupId": session["group_id"],
        "startedAt": now,
        "message": "Class has started"
    })
    
    logger.info(f"[Class] Session {session_id} started for group {session['group_id']}")
    
    return {
        "success": True,
        "message": "Class session started",
        "session_id": session_id,
        "started_at": now
    }


@admin_router.post("/sessions/{session_id}/end")
async def end_session(
    session_id: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """End a class session and archive attendance data"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    
    if session["status"] == "ended":
        raise HTTPException(status_code=400, detail="Session already ended")
    
    group_id = session["group_id"]
    group = db.get_group(group_id)
    group_name = group.get("name", "Unknown") if group else "Unknown"
    
    # Update session status
    now = datetime.now().isoformat()
    session["status"] = "ended"
    session["ended_at"] = now
    
    # Get attendance records from this session's timeframe
    started_at_str = session.get("started_at")
    start_dt = None
    if started_at_str:
        try:
            start_dt = datetime.fromisoformat(started_at_str)
        except ValueError:
            start_dt = None
    
    # Get members and their attendance for this session period
    members = db.get_group_members(group_id)
    records_from_today = []
    
    if start_dt:
        attendance_records = db.get_records(group_id=group_id, start_date=start_dt)
        present_persons = set(r["person_id"] for r in attendance_records)
        
        for member in members:
            person_id = member["person_id"]
            is_present = person_id in present_persons
            
            # Find the record for this person
            person_record = next((r for r in attendance_records if r["person_id"] == person_id), None)
            
            records_from_today.append({
                "person_id": person_id,
                "person_name": member.get("name", person_id),
                "enrollment_no": member.get("enrollment_no"),
                "status": "present" if is_present else "absent",
                "check_in_time": person_record["timestamp"] if person_record else None,
                "is_late": False,  # Could be calculated based on settings
                "late_minutes": 0,
                "confidence": person_record.get("confidence") if person_record else None,
                "notes": None,
            })
    
    # Archive this session
    h_db.archive_session(
        session_id=session_id,
        group_id=group_id,
        group_name=group_name,
        session_name=session.get("name", f"Class Session - {group_name}"),
        started_at=session.get("started_at"),
        ended_at=now,
        attendance_records=records_from_today,
        subject_name=session.get("subject_name"),
    )
    logger.info(f"[Class] Archived session {session_id} with {len(records_from_today)} records")
    
    # Remove from active sessions (now it's in history)
    del active_sessions[session_id]
    
    # Broadcast status update
    await broadcast_class_status({
        "status": "ended",
        "sessionId": session_id,
        "groupId": session["group_id"],
        "startedAt": session.get("started_at"),
        "message": "Class has ended"
    })
    
    logger.info(f"[Class] Session {session_id} ended")
    
    return {
        "success": True,
        "message": "Class session ended and archived",
        "session_id": session_id,
        "ended_at": now,
        "archived_records": len(records_from_today)
    }


@admin_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    del active_sessions[session_id]
    
    # Broadcast status update
    await broadcast_class_status({
        "status": "waiting",
        "sessionId": None,
        "groupId": None,
        "startedAt": None,
        "message": "Session deleted"
    })
    
    return {"success": True, "message": "Session deleted"}


class QuickStartRequest(BaseModel):
    enable_liveness: bool = True
    subject_id: Optional[str] = None


# Quick action endpoints for admin
@admin_router.post("/quick-start/{group_id}")
async def quick_start_class(
    group_id: str,
    request: QuickStartRequest = QuickStartRequest(),
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Quick start: Create and immediately start a class session.
    Clears previous session data for a fresh start (data is NOT archived here - only on end)."""
    # Verify group exists
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    
    # Check if group already has an active session for this subject
    existing_session = get_active_session_for_group(group_id, request.subject_id)
    if existing_session:
        error_msg = f"Group already has an active session for this subject" if request.subject_id else "Group already has an active general session"
        raise HTTPException(
            status_code=400, 
            detail=error_msg
        )
    
    # Resolve subject name if subject_id provided
    subject_name = None
    if request.subject_id:
        subjects = db.get_subjects(group_id)
        subject = next((s for s in subjects if s["id"] == request.subject_id), None)
        if subject:
            subject_name = subject["name"]
    
    # Clear current session data for fresh start (don't archive - that happens on end)
    db.clear_group_session_data(group_id)
    logger.info(f"[Class] Reset attendance data for group {group_id}")
    
    session_id = generate_session_id()
    now = datetime.now().isoformat()
    
    session = {
        "group_id": group_id,
        "name": group.get("name", "Class Session"),
        "subject_id": request.subject_id,
        "subject_name": subject_name,
        "status": "active",
        "started_at": now,
        "ended_at": None,
        "created_at": now,
        "enable_liveness": request.enable_liveness,
    }
    
    active_sessions[session_id] = session
    
    # Broadcast status update
    await broadcast_class_status({
        "status": "active",
        "sessionId": session_id,
        "groupId": group_id,
        "startedAt": now,
        "enableLiveness": request.enable_liveness,
        "subjectName": subject_name,
        "message": f"Class started for {session['name']}"
    })
    
    logger.info(f"[Class] Quick start: Session {session_id} for group {group_id} subject={subject_name} (liveness={'ON' if request.enable_liveness else 'OFF'})")
    
    return {
        "success": True,
        "message": "Class started",
        "session_id": session_id,
        "group_id": group_id,
        "started_at": now,
        "subject_name": subject_name,
        "enable_liveness": request.enable_liveness
    }


@admin_router.post("/end-all")
async def end_all_sessions(
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """End all active sessions and archive their attendance data"""
    now = datetime.now().isoformat()
    ended_count = 0
    archived_count = 0
    sessions_to_remove = []
    
    for session_id, session in active_sessions.items():
        if session["status"] in ["waiting", "active"]:
            group_id = session["group_id"]
            group = db.get_group(group_id)
            group_name = group.get("name", "Unknown") if group else "Unknown"
            
            session["status"] = "ended"
            session["ended_at"] = now
            ended_count += 1
            
            # Archive attendance data
            started_at_str = session.get("started_at")
            records_from_session = []
            if started_at_str:
                try:
                    start_dt = datetime.fromisoformat(started_at_str)
                    members = db.get_group_members(group_id)
                    attendance_records = db.get_records(group_id=group_id, start_date=start_dt)
                    present_persons = set(r["person_id"] for r in attendance_records)
                    
                    for member in members:
                        person_id = member["person_id"]
                        is_present = person_id in present_persons
                        person_record = next((r for r in attendance_records if r["person_id"] == person_id), None)
                        records_from_session.append({
                            "person_id": person_id,
                            "person_name": member.get("name", person_id),
                            "enrollment_no": member.get("enrollment_no"),
                            "status": "present" if is_present else "absent",
                            "check_in_time": person_record["timestamp"] if person_record else None,
                            "is_late": False,
                            "late_minutes": 0,
                            "confidence": person_record.get("confidence") if person_record else None,
                            "notes": None,
                        })
                except Exception as e:
                    logger.error(f"Error archiving session {session_id}: {e}")
            
            h_db.archive_session(
                session_id=session_id,
                group_id=group_id,
                group_name=group_name,
                session_name=session.get("name", f"Class Session - {group_name}"),
                started_at=session.get("started_at"),
                ended_at=now,
                attendance_records=records_from_session,
                subject_name=session.get("subject_name"),
            )
            archived_count += len(records_from_session)
            sessions_to_remove.append(session_id)
    
    # Remove archived sessions from active
    for sid in sessions_to_remove:
        del active_sessions[sid]
    
    # Broadcast status update
    await broadcast_class_status({
        "status": "ended",
        "sessionId": None,
        "groupId": None,
        "startedAt": None,
        "message": "All classes ended"
    })
    
    return {
        "success": True,
        "message": f"Ended {ended_count} session(s), archived {archived_count} records",
        "ended_at": now
    }


# History endpoints
@admin_router.get("/history")
async def get_attendance_history(
    group_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """Get attendance session history"""
    sessions = h_db.get_session_history(group_id=group_id, limit=limit, offset=offset)
    return {
        "success": True,
        "sessions": sessions,
        "count": len(sessions),
    }


@admin_router.get("/history/{session_id}")
async def get_history_session_detail(
    session_id: str,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """Get detailed attendance records for a specific archived session"""
    records = h_db.get_session_attendance(session_id)
    return {
        "success": True,
        "session_id": session_id,
        "records": records,
        "count": len(records),
    }


@admin_router.get("/history/student/{person_id}")
async def get_student_attendance_history(
    person_id: str,
    group_id: Optional[str] = None,
    limit: int = 50,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """Get attendance history for a specific student"""
    records = h_db.get_student_history(person_id=person_id, group_id=group_id, limit=limit)
    return {
        "success": True,
        "person_id": person_id,
        "records": records,
        "count": len(records),
    }


@admin_router.get("/history/stats/{group_id}")
async def get_group_history_stats(
    group_id: str,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """Get aggregate attendance statistics for a group"""
    stats = h_db.get_group_statistics(group_id)
    return {
        "success": True,
        **stats,
    }


@admin_router.delete("/history/{session_id}")
async def delete_history_session(
    session_id: str,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """Delete a session from history"""
    success = h_db.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found in history")
    return {
        "success": True,
        "message": "Session deleted from history",
    }


@admin_router.patch("/history/{session_id}/records/{person_id}")
async def update_history_attendance(
    session_id: str,
    person_id: str,
    update_data: AttendanceUpdate,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """
    Manually update attendance status for a record in history
    """
        
    success = h_db.update_attendance_status(
        session_id=session_id,
        person_id=person_id,
        status=update_data.status,
        is_late=update_data.is_late,
        late_minutes=update_data.late_minutes,
        notes=update_data.notes
    )
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail="Failed to update attendance. Record might not exist or person not found in session."
        )
        
    return {
        "success": True,
        "message": "Attendance updated"
    }
