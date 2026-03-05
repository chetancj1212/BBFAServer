"""
API Router Aggregator
Combines all API route modules into a single router
"""

from fastapi import APIRouter

from api.routes import detection, recognition, attendance, class_session, student

router = APIRouter()

router.include_router(detection.router, tags=["detection"])
router.include_router(recognition.router, tags=["recognition"])
router.include_router(attendance.admin_router, tags=["attendance"])
router.include_router(attendance.router, tags=["attendance"])
router.include_router(class_session.router, tags=["class"])
router.include_router(class_session.admin_router, tags=["class"])
router.include_router(student.router, tags=["student"])

# Import export router inside to avoid circular deps if any, or just import at top
from api.routes import export
router.include_router(export.router, tags=["export"])

from api.routes import panel
router.include_router(panel.router, tags=["panel"])
router.include_router(panel.admin_router, tags=["panel"])

__all__ = ["router"]
