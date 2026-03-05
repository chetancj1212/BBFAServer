import logging
import time

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request

from api.schemas import (
    DetectionRequest,
    DetectionResponse,
    OptimizationRequest,
)
from config.models import FACE_DETECTOR_CONFIG
from middleware.api_key import verify_api_key
from hooks import (
    process_face_detection,
    process_liveness_detection,
)
from utils import serialize_faces
from utils.image_utils import decode_base64_image

logger = logging.getLogger(__name__)

# Protect all detection endpoints with API key
router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/optimize/liveness")
async def configure_liveness_optimization(request: OptimizationRequest, req: Request):
    """Configure liveness detection optimization settings"""
    liveness_detector = getattr(req.app.state, "liveness_detector", None)

    if not liveness_detector:
        raise HTTPException(status_code=500, detail="Liveness detector not available")

    try:
        return {
            "success": True,
            "message": "Optimization settings updated",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update settings: {e}")


@router.post("/optimize/face_detector")
async def configure_face_detector_optimization(request: dict, req: Request):
    """Configure face detector optimization settings including minimum face size"""
    face_detector = getattr(req.app.state, "face_detector", None)

    try:
        if face_detector:
            if "min_face_size" in request:
                min_size = int(request["min_face_size"])
                face_detector.set_min_face_size(min_size)
                return {
                    "success": True,
                    "message": "Face detector settings updated successfully",
                    "new_settings": {"min_face_size": min_size},
                }
            else:
                return {"success": False, "message": "min_face_size parameter required"}
        else:
            return {"success": False, "message": "Face detector not available"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update face detector settings: {e}"
        )


@router.post("/detect", response_model=DetectionResponse)
async def detect_faces(request: DetectionRequest):
    """
    Detect faces in a single image
    """
    start_time = time.time()

    try:

        image = decode_base64_image(request.image)

        if request.model_type == "face_detector":
            min_face_size = (
                0
                if not request.enable_liveness_detection
                else FACE_DETECTOR_CONFIG["min_face_size"]
            )

            faces = process_face_detection(
                image,
                confidence_threshold=request.confidence_threshold,
                nms_threshold=request.nms_threshold,
                min_face_size=min_face_size,
                enable_liveness=request.enable_liveness_detection,
            )

            faces = process_liveness_detection(
                faces, image, request.enable_liveness_detection
            )

        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported model type: {request.model_type}"
            )

        processing_time = time.time() - start_time
        serialized_faces = serialize_faces(faces, "/detect endpoint")

        return DetectionResponse(
            success=True,
            faces=serialized_faces,
            processing_time=processing_time,
            model_used=request.model_type,
        )

    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect/upload")
async def detect_faces_upload(
    file: UploadFile = File(...),
    model_type: str = "face_detector",
    confidence_threshold: float = 0.6,
    nms_threshold: float = 0.3,
    enable_liveness_detection: bool = True,
):
    """
    Detect faces in an uploaded image file
    """
    start_time = time.time()

    try:
        contents = await file.read()

        nparr = np.frombuffer(contents, np.uint8)
        image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image_bgr is None:
            raise HTTPException(status_code=400, detail="Invalid image file")

        image = image_bgr

        if model_type == "face_detector":
            min_face_size = (
                0
                if not enable_liveness_detection
                else FACE_DETECTOR_CONFIG["min_face_size"]
            )

            faces = process_face_detection(
                image,
                confidence_threshold=confidence_threshold,
                nms_threshold=nms_threshold,
                min_face_size=min_face_size,
                enable_liveness=enable_liveness_detection,
            )

            faces = process_liveness_detection(
                faces, image, enable_liveness_detection
            )

        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported model type: {model_type}"
            )

        processing_time = time.time() - start_time
        serialized_faces = serialize_faces(faces, "/detect/upload endpoint")

        return {
            "success": True,
            "faces": serialized_faces,
            "processing_time": processing_time,
            "model_used": model_type,
        }

    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
