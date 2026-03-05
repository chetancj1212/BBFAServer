"""
Admin Panel Routes
Handles admin authentication and room/device management for BBFAPanel
"""

import json
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
import ulid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from middleware.api_key import verify_api_key
from api.dependencies import get_attendance_db
from database.attendance import AttendanceDatabaseManager

logger = logging.getLogger(__name__)

# Public router for initial login
router = APIRouter(prefix="/panel", tags=["panel"])

# Admin router for sensitive management actions
admin_router = APIRouter(prefix="/panel", tags=["panel"], dependencies=[Depends(verify_api_key)])

# ── Data directory ──
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
ADMINS_FILE = DATA_DIR / "admins.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ── File helpers ──

def _load_admins() -> list:
    _ensure_data_dir()
    if not ADMINS_FILE.exists():
        # Seed a default admin
        default = {
            "id": ulid.ulid(),
            "unique_id": "admin",
            "name": "Admin",
            "password_hash": _hash_password("admin123"),
            "created_at": datetime.now().isoformat(),
        }
        ADMINS_FILE.write_text(json.dumps([default], indent=2))
        logger.info("[Panel] Created default admin (unique_id=admin, password=admin123)")
        return [default]
    return json.loads(ADMINS_FILE.read_text())


def _save_admins(admins: list):
    _ensure_data_dir()
    ADMINS_FILE.write_text(json.dumps(admins, indent=2))





# ── Pydantic models ──

class LoginRequest(BaseModel):
    unique_id: str
    password: str


class AdminCreate(BaseModel):
    unique_id: str
    name: str
    password: str


class RoomCreate(BaseModel):
    room_no: str
    device_name: str
    description: Optional[str] = None


# ── Auth endpoints ──

@router.post("/login")
async def admin_login(data: LoginRequest):
    """Authenticate admin by unique ID + password"""
    admins = _load_admins()
    pw_hash = _hash_password(data.password)

    for admin in admins:
        if admin["unique_id"] == data.unique_id and admin["password_hash"] == pw_hash:
            return {
                "success": True,
                "admin": {
                    "id": admin["id"],
                    "unique_id": admin["unique_id"],
                    "name": admin["name"],
                    "created_at": admin["created_at"],
                },
            }

    raise HTTPException(status_code=401, detail="Invalid credentials")


@admin_router.get("/admins")
async def list_admins():
    """List all admin users"""
    admins = _load_admins()
    
    # Return admins without password_hash
    safe_admins = []
    for a in admins:
        safe_admin = {k: v for k, v in a.items() if k != "password_hash"}
        safe_admins.append(safe_admin)
        
    return {"admins": safe_admins}


class AdminUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None


@admin_router.put("/admins/{id}")
async def update_admin(id: str, data: AdminUpdate):
    """Update an admin user"""
    admins = _load_admins()
    
    # Find the admin to update
    admin_to_edit = next((a for a in admins if a["id"] == id), None)
    if not admin_to_edit:
        raise HTTPException(status_code=404, detail="Admin not found")
        
    if data.name:
        admin_to_edit["name"] = data.name
        
    if data.password:
        admin_to_edit["password_hash"] = _hash_password(data.password)
        
    _save_admins(admins)
    
    safe_admin = {k: v for k, v in admin_to_edit.items() if k != "password_hash"}
    return {"success": True, "admin": safe_admin}


@admin_router.post("/admins")
async def create_admin(data: AdminCreate):
    """Create a new admin user"""
    admins = _load_admins()

    # Check uniqueness
    if any(a["unique_id"] == data.unique_id for a in admins):
        raise HTTPException(status_code=400, detail="UniqueID already exists")

    admin = {
        "id": ulid.ulid(),
        "unique_id": data.unique_id,
        "name": data.name,
        "password_hash": _hash_password(data.password),
        "created_at": datetime.now().isoformat(),
    }
    admins.append(admin)
    _save_admins(admins)

    return {
        "success": True,
        "admin": {
            "id": admin["id"],
            "unique_id": admin["unique_id"],
            "name": admin["name"],
            "created_at": admin["created_at"],
        },
    }


@admin_router.delete("/admins/{id}")
async def delete_admin(id: str):
    """Delete an admin user"""
    admins = _load_admins()

    # Find the admin to delete
    admin_to_del = next((a for a in admins if a["id"] == id), None)
    if not admin_to_del:
        raise HTTPException(status_code=404, detail="Admin not found")

    # Prevent deleting the primary admin account
    if admin_to_del["unique_id"] == "admin":
        raise HTTPException(status_code=403, detail="Cannot delete the primary admin account")

    # Remove and save
    new_admins = [a for a in admins if a["id"] != id]
    _save_admins(new_admins)
    return {"success": True}


# ── Room endpoints ──

@admin_router.get("/rooms")
async def list_rooms(
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """List all rooms with their ESP device associations"""
    rooms = db.get_rooms()
    return {"rooms": rooms}


@admin_router.post("/rooms")
async def create_room(
    data: RoomCreate,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Create a new room → device mapping"""
    # Check uniqueness
    existing = db.get_rooms()
    if any(r["room_no"] == data.room_no for r in existing):
        raise HTTPException(status_code=400, detail="Room number already exists")

    room = {
        "id": ulid.ulid(),
        "room_no": data.room_no,
        "device_name": data.device_name,
        "description": data.description or "",
    }
    success = db.create_room(room)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create room")

    return {"success": True, "room": room}


@admin_router.delete("/rooms/{room_id}")
async def delete_room(
    room_id: str,
    db: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """Delete a room"""
    success = db.delete_room(room_id)
    if not success:
        raise HTTPException(status_code=404, detail="Room not found")
    return {"success": True}
