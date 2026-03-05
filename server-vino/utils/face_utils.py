import logging
import numpy as np

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_faces(faces: list, endpoint_name: str = "") -> list:
    """Serialize face detection results for API response"""
    serialized_faces = []
    for face in faces:
        # Validate required fields - handle both list and dict bbox formats
        if "bbox" not in face:
            logger.warning(f"Face missing bbox in {endpoint_name}: {face}")
            continue
        
        bbox = face["bbox"]
        
        # Normalize bbox to dict format for processing
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            bbox_dict = {"x": bbox[0], "y": bbox[1], "width": bbox[2], "height": bbox[3]}
        elif isinstance(bbox, dict):
            bbox_dict = bbox
        else:
            logger.warning(f"Face has invalid bbox format in {endpoint_name}: {face}")
            continue

        # Use bbox_original if present, otherwise use normalized bbox
        if "bbox_original" in face:
            bbox_orig = face["bbox_original"]
            if isinstance(bbox_orig, (list, tuple)) and len(bbox_orig) >= 4:
                bbox_orig = {"x": bbox_orig[0], "y": bbox_orig[1], "width": bbox_orig[2], "height": bbox_orig[3]}
            elif not isinstance(bbox_orig, dict):
                logger.warning(f"Face bbox_original is not valid: {face}")
                continue
        else:
            bbox_orig = bbox_dict

        # Validate bbox has all required fields
        required_bbox_fields = ["x", "y", "width", "height"]
        if not all(field in bbox_orig for field in required_bbox_fields):
            logger.warning(f"Face bbox missing required fields: {bbox_orig}")
            continue

        # Validate confidence is present
        if "confidence" not in face or face["confidence"] is None:
            logger.warning(f"Face missing confidence: {face}")
            continue

        # Serialize bbox as array [x, y, width, height]
        face["bbox"] = [
            bbox_orig["x"],
            bbox_orig["y"],
            bbox_orig["width"],
            bbox_orig["height"],
        ]

        # Validate liveness data if present
        if "liveness" in face:
            liveness = face["liveness"]
            if not isinstance(liveness, dict):
                logger.warning(f"Face liveness is not a dict: {face}")
                del face["liveness"]
            else:
                # Validate required liveness fields
                if "status" not in liveness:
                    logger.warning(f"Face liveness missing status: {liveness}")
                    del face["liveness"]
                elif "is_real" not in liveness:
                    logger.warning(f"Face liveness missing is_real: {liveness}")
                    del face["liveness"]

        # Remove embedding to reduce payload size
        if "embedding" in face:
            del face["embedding"]

        serialized_faces.append(face)

    return serialized_faces
