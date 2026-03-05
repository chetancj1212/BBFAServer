"""
Student Portal Routes
Handles student registration, login, and attendance marking

Fixes applied:
  #1  — Server-side BLE TOTP validation (ble_token replaces ble_verified)
  #3  — Fail loudly when face models unavailable (503 instead of silent skip)
  #4  — Dynamic device name from room/group linking
  #6  — app.state DI via Depends() instead of module globals
  #7  — Batch vectorized face matching
  #8  — Liveness detection wired into student flow
"""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Optional
import ulid
import base64
import cv2
import numpy as np

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from middleware.rate_limit import limiter
from api.dependencies import (
    get_attendance_db,
    get_face_db,
    get_face_detector,
    get_face_recognizer,
    get_inference_semaphore,
    get_thread_pool,
)
from database.attendance import AttendanceDatabaseManager
from database.face import FaceDatabaseManager
from hooks.face_processing import process_liveness_for_face_operation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/student", tags=["student"])

# ── Room data path (shared with panel) ──
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


# ── Pydantic models ──


class StudentLogin(BaseModel):
    enrollment_no: str
    group_id: str


class AttendanceMarkRequest(BaseModel):
    student_id: str
    session_id: str
    group_id: str
    image: str  # Base64 encoded image
    ble_token: str  # 8-digit TOTP token (Fix #1)
    device_name: str  # Dynamic device name (Fix #4)


class VerifyAndMarkRequest(BaseModel):
    """Request for verify-and-mark endpoint — identifies face and marks attendance"""
    session_id: str
    group_id: str
    image: str  # Base64 encoded image
    ble_token: str  # 8-digit TOTP token (Fix #1)
    device_name: str  # Dynamic device name (Fix #4)


class StudentResponse(BaseModel):
    id: str
    name: str
    enrollment_no: str
    group_id: str


class BleVerifyRequest(BaseModel):
    token: str  # 8-digit TOTP code as string
    device_name: str  # BLE device name resolved dynamically from room config


class ResolveDeviceRequest(BaseModel):
    """Request to resolve which BLE device to scan for, given an enrollment number."""
    enrollment_no: str


class FaceRegisterRequest(BaseModel):
    enrollment_no: str
    group_id: str
    image: str  # Base64 encoded image


# ── Helpers ──

def _generate_student_id() -> str:
    """Generate unique student ID"""
    return ulid.ulid()


def _decode_base64_image(base64_string: str):
    """Decode base64 image to numpy array"""
    try:
        image_data = base64.b64decode(base64_string)
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        logger.error(f"Failed to decode image: {e}")
        return None


def _validate_ble_token(token: str, device_name: str) -> bool:
    """
    Validate a BLE TOTP token server-side.
    Algorithm: SHA256(device_name + (unix_time // 30)), first 4 bytes as uint32 % 100_000_000.
    Accepts ±1 window (90 s tolerance) for clock drift.
    """
    now = int(time.time())
    for delta in [0, -1, 1]:
        time_step = (now // 30) + delta
        input_str = f"{device_name}{time_step}"
        hash_bytes = hashlib.sha256(input_str.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:4], "big")
        expected = hash_int % 100_000_000
        if token.strip().zfill(8) == str(expected).zfill(8):
            return True
    return False




def _resolve_active_class(device_name: str, db: AttendanceDatabaseManager) -> dict | None:
    """
    Resolve device_name → room → group(s) with that room → active session.
    Returns active class info dict or None.
    """
    from api.routes.class_session import active_sessions

    room = db.get_room_by_device_name(device_name)
    if not room:
        logger.info(f"[BLE] No room found for device_name={device_name}")
        return None

    room_id = room.get("id")
    room_no = room.get("room_no", "")

    # Find groups linked to this room
    all_groups = db.get_groups(active_only=True)
    linked_groups = [g for g in all_groups if g.get("room_id") == room_id]

    if not linked_groups:
        logger.info(f"[BLE] No groups linked to room_id={room_id} (device={device_name})")
        return None

    # Check if any linked group has an active session
    for group in linked_groups:
        group_id = group.get("id")
        for session_id, session in active_sessions.items():
            if session.get("group_id") == group_id and session.get("status") == "active":
                return {
                    "session_id": session_id,
                    "group_id": group_id,
                    "class_name": group.get("name", ""),
                    "subject_id": session.get("subject_id"),
                    "subject_name": session.get("subject_name"),
                    "room_no": room_no,
                    "started_at": session.get("started_at"),
                }

    logger.info(f"[BLE] No active session for groups linked to device={device_name}")
    return None


def _run_liveness_check(image, face, operation_name: str = "attendance"):
    """Run liveness detection. Returns (blocked: bool, reason: str | None)."""
    bbox_raw = face.get("bbox")
    if bbox_raw is None:
        return False, None
    # Normalize bbox to [x, y, w, h] list
    if isinstance(bbox_raw, dict):
        bbox = [bbox_raw.get("x", 0), bbox_raw.get("y", 0),
                bbox_raw.get("width", 0), bbox_raw.get("height", 0)]
    elif isinstance(bbox_raw, (list, tuple)):
        bbox = list(bbox_raw)
    else:
        return False, None
    return process_liveness_for_face_operation(
        image=image,
        bbox=bbox,
        enable_liveness_detection=True,
        operation_name=operation_name,
    )



@router.post("/login")
async def login_student(
    data: StudentLogin,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Login existing student by enrollment number"""
    members = db.get_group_members(data.group_id)
    for member in members:
        if member.get("enrollment_no") == data.enrollment_no.strip():
            return {
                "success": True,
                "message": "Login successful",
                "student": {
                    "id": member["person_id"],
                    "name": member["name"],
                    "enrollment_no": member.get("enrollment_no", ""),
                    "group_id": data.group_id,
                },
            }
    raise HTTPException(status_code=404, detail="Student not found. Please register first.")


@router.post("/mark-attendance")
@limiter.limit("3/minute")
async def mark_attendance(
    request: Request,
    data: AttendanceMarkRequest,
    att_db: AttendanceDatabaseManager = Depends(get_attendance_db),
    f_db: FaceDatabaseManager = Depends(get_face_db),
    detector=Depends(get_face_detector),
    recognizer=Depends(get_face_recognizer),
    semaphore: asyncio.Semaphore = Depends(get_inference_semaphore),
    pool=Depends(get_thread_pool),
):
    """
    Mark attendance with secure server-side checks:
    1. BLE TOTP validation (server-side)
    2. Face verification (with liveness) — runs in thread pool
    3. Timestamp
    """
    # Step 1: Server-side BLE TOTP validation (Fix #1)
    if not _validate_ble_token(data.ble_token, data.device_name):
        raise HTTPException(
            status_code=403,
            detail="BLE verification failed. Invalid or expired token.",
        )

    # Verify student exists and belongs to group
    member = att_db.get_member(data.student_id)
    if not member:
        raise HTTPException(status_code=404, detail="Student not found")
    if member.get("group_id") != data.group_id:
        raise HTTPException(status_code=403, detail="Student not in this class")

    # ── Subject Awareness Enforcement (Phase 3.1) ──
    from api.routes.class_session import active_sessions
    active_session = active_sessions.get(data.session_id)
    if active_session and active_session.get("subject_id"):
        student_subjects = att_db.get_student_subjects(data.student_id)
        enrolled_subject_ids = [s["id"] for s in student_subjects]
        if active_session["subject_id"] not in enrolled_subject_ids:
            logger.warning(f"[Student] {member['name']} not enrolled in {active_session['subject_name']}")
            raise HTTPException(
                status_code=403,
                detail=f"You are not enrolled in the active subject: {active_session['subject_name']}",
            )

    # Step 2: Face verification — fail loudly if models unavailable (Fix #3)
    if detector is None or recognizer is None:
        raise HTTPException(
            status_code=503,
            detail="Face recognition service not available. Please try again later.",
        )

    image = _decode_base64_image(data.image)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image data")

    try:
        loop = asyncio.get_running_loop()

        # Gate all AI inference behind the semaphore (Scalability Fix #2)
        async with semaphore:
            faces = await loop.run_in_executor(pool, partial(detector.detect_faces, image))
            if not faces or len(faces) == 0:
                raise HTTPException(status_code=400, detail="No face detected. Please ensure your face is visible.")
            if len(faces) > 1:
                raise HTTPException(status_code=400, detail="Multiple faces detected. Please ensure only you are in frame.")

            face = faces[0]

            # Liveness check (Fix #8) — offloaded to thread pool
            blocked, reason = await loop.run_in_executor(pool, partial(_run_liveness_check, image, face, "mark-attendance"))
            if blocked:
                raise HTTPException(
                    status_code=403,
                    detail=reason or "Liveness check failed. Please use a real face, not a photo or screen.",
                )

            landmarks = face.get("landmarks_5")
            if not landmarks:
                raise HTTPException(status_code=400, detail="Could not detect facial landmarks. Please try again.")

            embedding = await loop.run_in_executor(pool, partial(recognizer._extract_embedding, image, landmarks, face.get("bbox")))
            if embedding is None:
                raise HTTPException(status_code=400, detail="Could not process face. Please try again.")

        # Check stored face (DB ops are fast, no need for executor)
        stored_embedding = f_db.get_person(data.student_id)
        if stored_embedding is not None:
            similarity = float(np.dot(embedding, stored_embedding))
            if similarity < 0.5:
                logger.warning(f"[Student] Face mismatch for {data.student_id}, similarity: {similarity}")
                raise HTTPException(status_code=403, detail="Face does not match. Please try again.")
            logger.info(f"[Student] Face verified for {data.student_id}, similarity: {similarity}")
        else:
            f_db.add_person(data.student_id, embedding)
            logger.info(f"[Student] First time face registration for {data.student_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Student] Face verification error: {e}")
        raise HTTPException(status_code=500, detail="Face verification failed. Please try again.")

    # Step 3: Mark attendance
    now = datetime.now()
    record_id = ulid.ulid()
    try:
        att_db.add_record({
            "id": record_id,
            "person_id": data.student_id,
            "group_id": data.group_id,
            "timestamp": now,
            "confidence": 1.0,
            "location": f"session:{data.session_id}",
            "notes": "Student portal - BLE+Face verified",
            "is_manual": False,
        })

        date_str = now.strftime("%Y-%m-%d")
        session = att_db.get_session(data.student_id, date_str)
        session_data = {
            "id": session.get("id", ulid.ulid()) if session else ulid.ulid(),
            "person_id": data.student_id,
            "group_id": data.group_id,
            "date": date_str,
            "status": "present",
            "check_in_time": now,
            "total_hours": session.get("total_hours", 0) if session else 0,
            "is_late": session.get("is_late", False) if session else False,
            "late_minutes": session.get("late_minutes", 0) if session else 0,
        }
        att_db.upsert_session(session_data)

        logger.info(f"[Student] Attendance marked for {data.student_id} at {now}")
        return {
            "success": True,
            "message": "Attendance marked successfully",
            "record_id": record_id,
            "timestamp": now.isoformat(),
            "student_id": data.student_id,
        }
    except Exception as e:
        logger.error(f"[Student] Failed to mark attendance: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark attendance. Please try again.")


@router.get("/check-enrollment/{group_id}/{enrollment_no}")
async def check_enrollment(
    group_id: str,
    enrollment_no: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Check if enrollment number is already registered"""
    members = db.get_group_members(group_id)
    for member in members:
        if member.get("enrollment_no") == enrollment_no:
            return {"exists": True, "student": {"id": member["person_id"], "name": member["name"]}}
    return {"exists": False}


@router.get("/attendance-status/{student_id}/{session_id}")
async def get_attendance_status(
    student_id: str,
    session_id: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Check if student has already marked attendance for this session"""
    records = db.get_records(person_id=student_id)
    for record in records:
        if record.get("location", "").endswith(session_id):
            return {"marked": True, "timestamp": record.get("timestamp"), "record_id": record.get("id")}
    return {"marked": False}


@router.get("/has-face/{student_id}")
async def check_has_face(
    student_id: str,
    f_db: FaceDatabaseManager = Depends(get_face_db),
):
    """Check if a student has registered face data"""
    return {"has_face": f_db.has_face(student_id), "student_id": student_id}


@router.get("/lookup/{group_id}/{enrollment_no}")
async def lookup_student(
    group_id: str,
    enrollment_no: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
    f_db: FaceDatabaseManager = Depends(get_face_db),
):
    """Lookup student by enrollment number and return their details including face status"""
    members = db.get_group_members(group_id)
    for member in members:
        if member.get("enrollment_no") == enrollment_no.strip():
            student_id = member["person_id"]
            return {
                "found": True,
                "student": {
                    "id": student_id,
                    "name": member["name"],
                    "enrollment_no": member.get("enrollment_no", ""),
                    "group_id": group_id,
                    "has_face": f_db.has_face(student_id),
                },
            }
    raise HTTPException(status_code=404, detail="Student not found. Please register first.")


@router.post("/verify-ble")
async def verify_ble_token(
    data: BleVerifyRequest,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """
    Pre-check BLE TOTP token AND resolve the active class for this device.
    Returns which lecture/class is currently active for the scanned device.
    """
    valid = _validate_ble_token(data.token, data.device_name)
    if valid:
        logger.info(f"[BLE] ✅ Token valid for device={data.device_name}")
    else:
        logger.warning(f"[BLE] ❌ Token invalid for device={data.device_name}")
        return {"valid": False, "active_class": None}

    # Resolve device_name → room → group → active session
    active_class = _resolve_active_class(data.device_name, db)

    return {"valid": True, "active_class": active_class}


@router.post("/resolve-device")
async def resolve_device(
    data: ResolveDeviceRequest,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """
    Given an enrollment number, find which group the student belongs to,
    check if that group has an active class session, and return the BLE
    device name to scan for + active class info.
    """
    from api.routes.class_session import active_sessions

    enrollment = data.enrollment_no.strip()
    if not enrollment:
        raise HTTPException(status_code=400, detail="Enrollment number is required.")

    # Search all active groups for this enrollment number
    all_groups = db.get_groups(active_only=True)
    rooms = db.get_rooms()

    for group in all_groups:
        group_id = group.get("id")
        members = db.get_group_members(group_id)
        student = None
        for member in members:
            if member.get("enrollment_no") == enrollment:
                student = member
                break
        if not student:
            continue

        # Student found in this group — check for active session
        for session_id, session in active_sessions.items():
            if session.get("group_id") == group_id and session.get("status") == "active":
                # Resolve device name for this group's room
                room_id = group.get("room_id")
                device_name = None
                room_no = None
                if room_id:
                    room = next((r for r in rooms if r.get("id") == room_id), None)
                    if room:
                        device_name = room.get("device_name")
                        room_no = room.get("room_no", "")

                if not device_name:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No device linked to class '{group.get('name', '')}'."
                    )

                return {
                    "found": True,
                    "student": {
                        "id": student["person_id"],
                        "name": student["name"],
                        "enrollment_no": enrollment,
                    },
                    "device_name": device_name,
                    "active_class": {
                        "session_id": session_id,
                        "group_id": group_id,
                        "class_name": group.get("name", ""),
                        "subject_name": session.get("subject_name"),
                        "room_no": room_no,
                        "started_at": session.get("started_at"),
                    },
                }

    # Check if student exists at all (but no active class)
    for group in all_groups:
        members = db.get_group_members(group.get("id"))
        for member in members:
            if member.get("enrollment_no") == enrollment:
                raise HTTPException(
                    status_code=404,
                    detail="No active class found for your enrollment."
                )

    raise HTTPException(status_code=404, detail="Enrollment number not found.")


@router.get("/device-name/{group_id}")
async def get_device_name(
    group_id: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """
    Resolve group → room → device_name (Fix #4).
    Allows the Flutter app to discover which BLE device to scan for.
    """
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    room_id = group.get("room_id")
    if not room_id:
        raise HTTPException(
            status_code=404,
            detail="No room linked to this class. Ask admin to link a room.",
        )

    rooms = db.get_rooms()
    for room in rooms:
        if room.get("id") == room_id:
            dn = room.get("device_name")
            if not dn:
                raise HTTPException(
                    status_code=404,
                    detail="Room has no device configured.",
                )
            return {
                "device_name": dn,
                "room_no": room.get("room_no", ""),
                "source": "room",
            }

    raise HTTPException(
        status_code=404,
        detail="Linked room not found in database. Ask admin to reconfigure.",
    )


@router.post("/register-face")
@limiter.limit("5/minute")
async def register_face(
    request: Request,
    data: FaceRegisterRequest,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
    f_db: FaceDatabaseManager = Depends(get_face_db),
    detector=Depends(get_face_detector),
    recognizer=Depends(get_face_recognizer),
    semaphore: asyncio.Semaphore = Depends(get_inference_semaphore),
    pool=Depends(get_thread_pool),
):
    """Register or update face for an existing student."""
    members = db.get_group_members(data.group_id)
    student = None
    for member in members:
        if member.get("enrollment_no") == data.enrollment_no.strip():
            student = member
            break

    if not student:
        raise HTTPException(status_code=404, detail="Student not found. Please register with your details first.")

    student_id = student["person_id"]
    student_name = student["name"]
    is_update = f_db.has_face(student_id)

    image = _decode_base64_image(data.image)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image data")

    # Fail loudly if models unavailable (Fix #3)
    if detector is None or recognizer is None:
        raise HTTPException(status_code=503, detail="Face recognition service not available. Please try again later.")

    try:
        loop = asyncio.get_running_loop()

        # Gate AI inference behind semaphore (Scalability Fix #2)
        async with semaphore:
            faces = await loop.run_in_executor(pool, partial(detector.detect_faces, image))
            if not faces or len(faces) == 0:
                raise HTTPException(status_code=400, detail="No face detected. Please ensure your face is clearly visible.")
            if len(faces) > 1:
                raise HTTPException(status_code=400, detail="Multiple faces detected. Please ensure only you are in frame.")

            face = faces[0]

            # Liveness check (Fix #8) — offloaded to thread pool
            blocked, reason = await loop.run_in_executor(pool, partial(_run_liveness_check, image, face, "register-face"))
            if blocked:
                raise HTTPException(
                    status_code=403,
                    detail=reason or "Liveness check failed. Please use a real face, not a photo or screen.",
                )

            landmarks = face.get("landmarks_5")
            if not landmarks:
                raise HTTPException(status_code=400, detail="Could not detect facial landmarks. Please try again.")

            result = await loop.run_in_executor(pool, partial(recognizer.register_face, student_id, image, landmarks))
            if not result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=result.get("error", "Could not process face. Please try again with better lighting."),
                )

        action = "updated" if is_update else "registered"
        logger.info(f"[Student] Face {action} for {student_name} ({data.enrollment_no})")
        return {
            "success": True,
            "message": f"Face {action} successfully for {student_name}",
            "student": {"id": student_id, "name": student_name, "enrollment_no": data.enrollment_no},
            "is_update": is_update,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Student] Face registration error: {e}")
        raise HTTPException(status_code=500, detail="Face registration failed. Please try again.")


@router.post("/verify-and-mark")
@limiter.limit("3/minute")
async def verify_and_mark_attendance(
    request: Request,
    data: VerifyAndMarkRequest,
    att_db: AttendanceDatabaseManager = Depends(get_attendance_db),
    f_db: FaceDatabaseManager = Depends(get_face_db),
    detector=Depends(get_face_detector),
    recognizer=Depends(get_face_recognizer),
    semaphore: asyncio.Semaphore = Depends(get_inference_semaphore),
    pool=Depends(get_thread_pool),
):
    """
    Verify face and mark attendance in one step.
    1. Server-side BLE TOTP validation
    2. Detect + liveness check — runs in thread pool (Scalability Fix #1)
    3. Batch vectorized match against group members
    4. Mark attendance
    """
    # Step 1: Server-side BLE TOTP validation (Fix #1)
    if not _validate_ble_token(data.ble_token, data.device_name):
        raise HTTPException(
            status_code=403,
            detail="BLE verification failed. Invalid or expired token.",
        )

    # Fail loudly if models unavailable (Fix #3)
    if detector is None or recognizer is None:
        raise HTTPException(
            status_code=503,
            detail="Face recognition service not available. Please try again later.",
        )

    image = _decode_base64_image(data.image)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image data")

    try:
        loop = asyncio.get_running_loop()

        # Gate AI inference behind semaphore (Scalability Fix #2)
        async with semaphore:
            faces = await loop.run_in_executor(pool, partial(detector.detect_faces, image))
            if not faces or len(faces) == 0:
                raise HTTPException(status_code=400, detail="No face detected. Please ensure your face is clearly visible.")
            if len(faces) > 1:
                raise HTTPException(status_code=400, detail="Multiple faces detected. Please ensure only you are in frame.")

            face = faces[0]

            # Liveness check (Fix #8) — offloaded to thread pool
            blocked, reason = await loop.run_in_executor(pool, partial(_run_liveness_check, image, face, "verify-and-mark"))
            if blocked:
                raise HTTPException(
                    status_code=403,
                    detail=reason or "Liveness check failed. Please use a real face, not a photo or screen.",
                )

            landmarks = face.get("landmarks_5")
            if not landmarks:
                raise HTTPException(status_code=400, detail="Could not detect facial landmarks. Please try again.")

            embedding = await loop.run_in_executor(pool, partial(recognizer._extract_embedding, image, landmarks, face.get("bbox")))
            if embedding is None:
                raise HTTPException(status_code=400, detail="Could not process face. Please try again.")

        # ── Batch vectorized face matching (Fix #7) — fast numpy, no executor needed ──
        members = att_db.get_group_members(data.group_id)
        if not members:
            raise HTTPException(status_code=404, detail="No students registered in this class.")

        person_ids = [m["person_id"] for m in members]
        embeddings_map = f_db.get_persons_by_ids(person_ids)

        if not embeddings_map:
            raise HTTPException(status_code=404, detail="No registered faces in this class. Please register your face first.")

        # Build matrix and compute similarities in one shot
        ids = list(embeddings_map.keys())
        matrix = np.stack([embeddings_map[pid] for pid in ids])  # (N, D)
        similarities = np.dot(matrix, embedding)  # (N,)

        match_threshold = 0.45
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score < match_threshold:
            raise HTTPException(status_code=404, detail="Face not recognized. Please register your face first.")

        best_match_id = ids[best_idx]
        matched_member = next((m for m in members if m["person_id"] == best_match_id), None)
        if not matched_member:
            raise HTTPException(status_code=404, detail="Student record not found.")

        logger.info(f"[Student] Face matched: {matched_member['name']} (similarity: {best_score:.3f})")

        # ── Subject Awareness Enforcement (Phase 3.1) ──
        from api.routes.class_session import active_sessions
        active_session = active_sessions.get(data.session_id)
        if active_session and active_session.get("subject_id"):
            student_subjects = att_db.get_student_subjects(best_match_id)
            enrolled_subject_ids = [s["id"] for s in student_subjects]
            if active_session["subject_id"] not in enrolled_subject_ids:
                logger.warning(f"[Student] {matched_member['name']} not enrolled in {active_session['subject_name']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"You are not enrolled in the active subject: {active_session['subject_name']}",
                )

        # Step 4: Mark attendance
        now = datetime.now()
        record_id = ulid.ulid()

        existing_records = att_db.get_records(person_id=best_match_id)
        is_duplicate = any(r.get("location", "").endswith(data.session_id) for r in existing_records)

        att_db.add_record({
            "id": record_id,
            "person_id": best_match_id,
            "group_id": data.group_id,
            "timestamp": now,
            "confidence": best_score,
            "location": f"session:{data.session_id}",
            "notes": "Student portal - BLE+Face verified" + (" (duplicate)" if is_duplicate else ""),
            "is_manual": False,
        })

        if not is_duplicate:
            date_str = now.strftime("%Y-%m-%d")
            session = att_db.get_session(best_match_id, date_str)
            if not session:
                att_db.upsert_session({
                    "id": ulid.ulid(),
                    "person_id": best_match_id,
                    "group_id": data.group_id,
                    "date": date_str,
                    "status": "present",
                    "check_in_time": now,
                    "total_hours": 0,
                    "is_late": False,
                    "late_minutes": 0,
                })

        logger.info(f"[Student] Attendance marked for {matched_member['name']} at {now}")
        return {
            "success": True,
            "message": "Attendance marked successfully",
            "student": {
                "id": best_match_id,
                "name": matched_member["name"],
                "enrollment_no": matched_member.get("enrollment_no", ""),
            },
            "record_id": record_id,
            "timestamp": now.isoformat(),
            "is_duplicate": is_duplicate,
            "confidence": round(best_score, 3),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Student] Verify and mark error: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify face. Please try again.")
