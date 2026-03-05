"""
Export Routes
Export class session data to CSV/Excel formats
"""

import csv
import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from database.history import AttendanceHistoryManager
from api.dependencies import get_history_db

from middleware.api_key import verify_api_key

router = APIRouter(prefix="/class/export", tags=["export"], dependencies=[Depends(verify_api_key)])


@router.get("/{session_id}")
async def export_session_csv(
    session_id: str,
    h_db: AttendanceHistoryManager = Depends(get_history_db),
):
    """
    Export session attendance to CSV.
    The user can open this file in Excel.
    """
    # Get session details
    # We need to find the session metadata first (usually we have get_session_history but that lists all)
    # Ideally logic would be: get details -> get records -> format CSV
    # Since get_session_attendance only returns records, we might need a way to get single session meta from history
    # For now we'll just get records and rely on that.
    
    records = h_db.get_session_attendance(session_id)
    if not records:
        raise HTTPException(status_code=404, detail="Session not found or has no records")

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Student Name", 
        "Enrollment No", 
        "Status", 
        "Check-in Time", 
        "Late (Minutes)", 
        "Confidence",
        "Notes"
    ])

    # Data
    for record in records:
        # Format check-in time
        check_in = record.get("check_in_time")
        if check_in:
            try:
                dt = datetime.fromisoformat(check_in.replace("Z", "+00:00"))
                check_in_formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                check_in_formatted = check_in
        else:
            check_in_formatted = "-"

        # Format Late
        is_late = record.get("is_late", False)
        late_mins = record.get("late_minutes", 0) if is_late else 0
        
        status = record.get("status", "absent").upper()

        writer.writerow([
            record.get("person_name") or "Unknown",
            record.get("enrollment_no") or "-",
            status,
            check_in_formatted,
            f"{late_mins} min" if is_late else "-",
            f"{record.get('confidence', 0):.2f}" if record.get("confidence") else "-",
            record.get("notes") or ""
        ])

    output.seek(0)
    
    # Filename
    filename = f"Attendance_{session_id[:8]}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv"
    )
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    
    return response
