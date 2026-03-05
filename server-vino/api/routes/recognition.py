from fastapi import APIRouter, HTTPException, Depends

from middleware.api_key import verify_api_key
from api.dependencies import (
    get_attendance_db,
    get_face_db,
    get_face_recognizer,
    get_liveness_detector,
)
from database.attendance import AttendanceDatabaseManager
from database.face import FaceDatabaseManager

from api.schemas import (
    FaceRecognitionRequest,
    FaceRecognitionResponse,
    FaceRegistrationRequest,
    FaceRegistrationResponse,
    PersonUpdateRequest,
    SimilarityThresholdRequest,
    BatchFaceRecognitionRequest,
    BatchFaceRecognitionResponse,
    FaceRecognitionResult,
    MultiAngleRegistrationRequest,
    MultiAngleRegistrationResponse,
    AngleValidationResult,
    PoseEstimationRequest,
    PoseEstimationResponse,
)
from hooks import process_liveness_for_face_operation
from utils.image_utils import decode_base64_image
from utils.pose_utils import (
    estimate_face_pose,
    classify_face_angle,
    is_angle_valid_for_recognition,
    ANGLE_THRESHOLDS,
)
import logging
import time

logger = logging.getLogger(__name__)

# Protect all recognition endpoints with API key
router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post("/face/recognize", response_model=FaceRecognitionResponse)
async def recognize_face(
    request: FaceRecognitionRequest,
    face_recognizer=Depends(get_face_recognizer),
    attendance_database: AttendanceDatabaseManager = Depends(get_attendance_db),
):
    """
    Recognize a face using face recognizer with liveness detection validation
    """
    logger.info(f"[DEBUG] /face/recognize endpoint called! group_id={request.group_id}, has_landmarks={request.landmarks_5 is not None}")
    
    start_time = time.time()

    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        image = decode_base64_image(request.image)

        # Check liveness detection
        should_block, error_msg = process_liveness_for_face_operation(
            image, request.bbox, request.enable_liveness_detection, "Recognition"
        )
        if should_block:
            processing_time = time.time() - start_time
            return FaceRecognitionResponse(
                success=False,
                person_id=None,
                similarity=0.0,
                processing_time=processing_time,
                error=error_msg,
            )

        # Get landmarks_5 for face_recognizer (required for face alignment)
        landmarks_5 = request.landmarks_5
        if landmarks_5 is None:
            raise HTTPException(
                status_code=400,
                detail="Landmarks required for face recognition",
            )

        allowed_person_ids = None
        if request.group_id and attendance_database:
            allowed_person_ids = attendance_database.get_group_person_ids(
                request.group_id
            )
        
        # Pass bbox for small face enhancement (improves accuracy at distance)
        result = face_recognizer.recognize_face(
            image, landmarks_5, allowed_person_ids, bbox=request.bbox
        )

        processing_time = time.time() - start_time

        return FaceRecognitionResponse(
            success=result["success"],
            person_id=result.get("person_id"),
            similarity=result.get("similarity", 0.0),
            processing_time=processing_time,
            error=result.get("error"),
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Face recognition error: {e}")
        return FaceRecognitionResponse(
            success=False,
            person_id=None,
            similarity=0.0,
            processing_time=processing_time,
            error=str(e),
        )


@router.post("/face/recognize-batch", response_model=BatchFaceRecognitionResponse)
async def recognize_faces_batch(
    request: BatchFaceRecognitionRequest,
    face_recognizer=Depends(get_face_recognizer),
    attendance_database: AttendanceDatabaseManager = Depends(get_attendance_db),
    liveness_detector=Depends(get_liveness_detector),
):
    """
    Recognize multiple faces in a single image using batch processing.
    More efficient than calling /face/recognize multiple times.
    """
    start_time = time.time()

    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        if not request.faces:
            processing_time = time.time() - start_time
            return BatchFaceRecognitionResponse(
                success=True,
                results=[],
                processing_time=processing_time,
            )

        image = decode_base64_image(request.image)

        # Prepare faces data for batch processing
        faces_data = []
        liveness_blocked_indices = set()

        for i, face in enumerate(request.faces):
            # Optional: Check liveness for each face if enabled
            if request.enable_liveness_detection and liveness_detector:
                should_block, error_msg = process_liveness_for_face_operation(
                    image, face.bbox, True, "Recognition"
                )
                if should_block:
                    liveness_blocked_indices.add(i)
                    continue

            faces_data.append({
                "landmarks_5": face.landmarks_5,
                "track_id": face.track_id,
                "bbox": face.bbox,
                "original_index": i,
            })

        # Get allowed person IDs if group filtering is requested
        allowed_person_ids = None
        if request.group_id and attendance_database:
            allowed_person_ids = attendance_database.get_group_person_ids(request.group_id)

        # Perform batch recognition
        recognition_results = []
        if faces_data:
            recognition_results = face_recognizer.recognize_faces_batch(
                image, faces_data, allowed_person_ids
            )

        # Build final results list maintaining original order
        results = []
        recognition_idx = 0
        
        for i, face in enumerate(request.faces):
            if i in liveness_blocked_indices:
                # Face was blocked by liveness detection
                results.append(FaceRecognitionResult(
                    track_id=face.track_id,
                    person_id=None,
                    similarity=0.0,
                    success=False,
                    error="Blocked: spoofed face detected",
                ))
            else:
                # Get recognition result
                if recognition_idx < len(recognition_results):
                    rec_result = recognition_results[recognition_idx]
                    results.append(FaceRecognitionResult(
                        track_id=rec_result.get("track_id"),
                        person_id=rec_result.get("person_id"),
                        similarity=rec_result.get("similarity", 0.0),
                        success=rec_result.get("success", False),
                        error=rec_result.get("error"),
                    ))
                    recognition_idx += 1
                else:
                    results.append(FaceRecognitionResult(
                        track_id=face.track_id,
                        person_id=None,
                        similarity=0.0,
                        success=False,
                        error="Recognition failed",
                    ))

        processing_time = time.time() - start_time

        return BatchFaceRecognitionResponse(
            success=True,
            results=results,
            processing_time=processing_time,
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Batch face recognition error: {e}")
        return BatchFaceRecognitionResponse(
            success=False,
            results=[],
            processing_time=processing_time,
            error=str(e),
        )


@router.post("/face/register", response_model=FaceRegistrationResponse)
async def register_person(
    request: FaceRegistrationRequest,
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Register a new person in the face database with liveness detection validation
    """
    start_time = time.time()

    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        image = decode_base64_image(request.image)

        # Check liveness detection
        should_block, error_msg = process_liveness_for_face_operation(
            image, request.bbox, request.enable_liveness_detection, "Registration"
        )
        if should_block:
            processing_time = time.time() - start_time
            return FaceRegistrationResponse(
                success=False,
                person_id=request.person_id,
                total_persons=0,
                processing_time=processing_time,
                error=error_msg,
            )

        # Get landmarks_5 for face_recognizer (required for face alignment)
        landmarks_5 = request.landmarks_5
        if landmarks_5 is None:
            raise HTTPException(
                status_code=400,
                detail="Landmarks required for face recognition",
            )

        result = face_recognizer.register_person(
            request.person_id, image, landmarks_5
        )

        processing_time = time.time() - start_time

        return FaceRegistrationResponse(
            success=result["success"],
            person_id=request.person_id,
            total_persons=result.get("total_persons", 0),
            processing_time=processing_time,
            error=result.get("error"),
        )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Person registration error: {e}")
        return FaceRegistrationResponse(
            success=False,
            person_id=request.person_id,
            total_persons=0,
            processing_time=processing_time,
            error=str(e),
        )


@router.delete("/face/person/{person_id}")
async def remove_person(
    person_id: str,
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Remove a person from the face database
    """
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        result = face_recognizer.remove_person(person_id)

        if result["success"]:
            return {
                "success": True,
                "message": f"Person {person_id} removed successfully",
                "total_persons": result.get("total_persons", 0),
            }
        else:
            raise HTTPException(
                status_code=404, detail=result.get("error", "Person not found")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Person removal error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove person: {e}")


@router.put("/face/person")
async def update_person(
    request: PersonUpdateRequest,
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Update a person's ID in the face database
    """
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        # Validate input
        if not request.old_person_id.strip() or not request.new_person_id.strip():
            raise HTTPException(
                status_code=400, detail="Both old and new person IDs must be provided"
            )

        if request.old_person_id.strip() == request.new_person_id.strip():
            raise HTTPException(
                status_code=400, detail="Old and new person IDs must be different"
            )

        # Update person ID using face recognizer method
        result = face_recognizer.update_person_id(
            request.old_person_id.strip(), request.new_person_id.strip()
        )

        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=404, detail=result.get("error", "Update failed")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Person update error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update person: {e}")


@router.get("/face/persons")
async def get_all_persons(
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Get list of all registered persons
    """
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        persons = face_recognizer.get_all_persons()
        stats = face_recognizer.get_stats()

        return {
            "success": True,
            "persons": persons,
            "total_count": len(persons),
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Get persons error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get persons: {e}")


@router.post("/face/threshold")
async def set_similarity_threshold(
    request: SimilarityThresholdRequest,
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Set similarity threshold for face recognition
    """
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        if not (0.0 <= request.threshold <= 1.0):
            raise HTTPException(
                status_code=400, detail="Threshold must be between 0.0 and 1.0"
            )

        face_recognizer.set_similarity_threshold(request.threshold)

        return {
            "success": True,
            "message": f"Similarity threshold updated to {request.threshold}",
            "threshold": request.threshold,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Threshold update error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update threshold: {e}")


@router.delete("/face/database")
async def clear_database(
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Clear all persons from the face database
    """
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        result = face_recognizer.clear_database()

        if result["success"]:
            return {
                "success": True,
                "message": "Face database cleared successfully",
                "total_persons": 0,
            }
        else:
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to clear database")
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database clear error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear database: {e}")


@router.get("/face/stats")
async def get_face_stats(
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Get face recognition statistics and configuration
    """
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")

        stats = face_recognizer.get_stats()

        # Return stats directly in the format expected by the Settings component
        return stats

    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@router.get("/face/liveness-threshold")
async def get_liveness_threshold(
    liveness_detector=Depends(get_liveness_detector),
):
    """
    Get the current liveness (anti-spoof) logit threshold.
    Range: -5.0 (lenient) to +5.0 (strict). Default: 0.0
    """
    try:
        if not liveness_detector:
            return {"success": True, "threshold": 0.0, "available": False}

        threshold = getattr(liveness_detector, "logit_threshold", 0.0)
        return {"success": True, "threshold": threshold, "available": True}

    except Exception as e:
        logger.error(f"Get liveness threshold error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get liveness threshold: {e}")


@router.post("/face/liveness-threshold")
async def set_liveness_threshold(
    request: SimilarityThresholdRequest,
    liveness_detector=Depends(get_liveness_detector),
):
    """
    Set the liveness (anti-spoof) logit threshold.
    Lower = more lenient (fewer real faces rejected, but more spoofs may pass).
    Higher = stricter (more spoofs rejected, but real faces may be falsely rejected).
    Range: -5.0 to +5.0
    """
    try:
        if not liveness_detector:
            raise HTTPException(status_code=503, detail="Liveness detector not available")

        if not (-5.0 <= request.threshold <= 5.0):
            raise HTTPException(
                status_code=400, detail="Liveness threshold must be between -5.0 and 5.0"
            )

        liveness_detector.logit_threshold = request.threshold

        return {
            "success": True,
            "message": f"Liveness threshold updated to {request.threshold}",
            "threshold": request.threshold,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Liveness threshold update error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update liveness threshold: {e}")


@router.post("/face/estimate-pose", response_model=PoseEstimationResponse)
async def estimate_pose(request: PoseEstimationRequest):
    """
    Estimate face pose from landmarks.
    Use this to validate face angle before registration.
    """
    try:
        result = classify_face_angle(request.landmarks_5, request.expected_angle)
        pose = result["pose"]
        
        return PoseEstimationResponse(
            success=True,
            yaw=pose["yaw"],
            pitch=pose["pitch"],
            roll=pose["roll"],
            direction=result["direction"],
            is_valid=result["is_valid"],
            expected_angle=request.expected_angle,
            error=result.get("error"),
        )
        
    except Exception as e:
        logger.error(f"Pose estimation error: {e}")
        return PoseEstimationResponse(
            success=False,
            yaw=0.0,
            pitch=0.0,
            roll=0.0,
            direction="unknown",
            is_valid=False,
            expected_angle=request.expected_angle or "front",
            error=str(e),
        )


@router.post("/face/register-multi-angle", response_model=MultiAngleRegistrationResponse)
async def register_multi_angle(
    request: MultiAngleRegistrationRequest,
    face_recognizer=Depends(get_face_recognizer),
):
    """
    Register a person with multiple face angles for improved recognition accuracy.
    
    Expects 3 photos: front, left (~30°), right (~30°).
    Validates each angle and rejects if face is not positioned correctly.
    """
    start_time = time.time()
    angle_validations = []
    embeddings_stored = 0
    
    try:
        if not face_recognizer:
            raise HTTPException(status_code=500, detail="Face recognizer not available")
        
        # Validate we have all required angles
        required_angles = {"front", "left", "right"}
        provided_angles = {face.angle for face in request.faces}
        
        missing_angles = required_angles - provided_angles
        if missing_angles:
            processing_time = time.time() - start_time
            return MultiAngleRegistrationResponse(
                success=False,
                person_id=request.person_id,
                total_persons=0,
                processing_time=processing_time,
                angle_validations=[],
                embeddings_stored=0,
                error=f"Missing required angles: {', '.join(missing_angles)}",
            )
        
        # Process each angle
        valid_embeddings = []
        
        for face_data in request.faces:
            angle = face_data.angle
            
            # Validate landmarks exist
            if not face_data.landmarks_5 or len(face_data.landmarks_5) != 5:
                logger.warning(f"Invalid landmarks for {angle}: {face_data.landmarks_5}")
                angle_result = AngleValidationResult(
                    angle=angle,
                    is_valid=False,
                    detected_angle=0.0,
                    direction="unknown",
                    error=f"Invalid landmarks data for {angle} angle",
                )
                angle_validations.append(angle_result)
                continue
            
            # Validate pose
            try:
                validation = classify_face_angle(face_data.landmarks_5, angle)
                pose = validation["pose"]
            except Exception as e:
                logger.error(f"Pose validation failed for {angle}: {e}")
                angle_result = AngleValidationResult(
                    angle=angle,
                    is_valid=False,
                    detected_angle=0.0,
                    direction="unknown",
                    error=f"Pose validation error: {str(e)}",
                )
                angle_validations.append(angle_result)
                continue
            
            angle_result = AngleValidationResult(
                angle=angle,
                is_valid=validation["is_valid"],
                detected_angle=pose["yaw"],
                direction=validation["direction"],
                error=validation.get("error"),
            )
            angle_validations.append(angle_result)
            
            if not validation["is_valid"]:
                continue  # Skip this angle, will fail overall
            
            # Decode image
            try:
                image = decode_base64_image(face_data.image)
            except Exception as e:
                logger.error(f"Image decode failed for {angle}: {e}")
                angle_result.is_valid = False
                angle_result.error = f"Image decode error: {str(e)}"
                continue
            
            # Check liveness if enabled
            if request.enable_liveness_detection:
                should_block, error_msg = process_liveness_for_face_operation(
                    image, face_data.bbox, True, f"Registration ({angle})"
                )
                if should_block:
                    angle_result.is_valid = False
                    angle_result.error = error_msg
                    continue
            
            # Extract embedding
            try:
                embedding = face_recognizer._extract_embedding(
                    image, face_data.landmarks_5, face_data.bbox
                )
            except Exception as e:
                logger.error(f"Embedding extraction failed for {angle}: {e}")
                embedding = None
            
            if embedding is not None:
                valid_embeddings.append({
                    "angle": angle,
                    "embedding": embedding,
                })
                logger.info(f"Successfully extracted embedding for {angle}")
            else:
                logger.warning(f"Embedding extraction returned None for {angle}")
        
        # Check if all angles passed validation
        failed_angles = [v for v in angle_validations if not v.is_valid]
        if failed_angles:
            processing_time = time.time() - start_time
            error_messages = [f"{v.angle}: {v.error}" for v in failed_angles if v.error]
            return MultiAngleRegistrationResponse(
                success=False,
                person_id=request.person_id,
                total_persons=0,
                processing_time=processing_time,
                angle_validations=angle_validations,
                embeddings_stored=0,
                error=f"Angle validation failed. {'; '.join(error_messages)}",
            )
        
        # Check if we have valid embeddings
        if len(valid_embeddings) < 3:
            processing_time = time.time() - start_time
            return MultiAngleRegistrationResponse(
                success=False,
                person_id=request.person_id,
                total_persons=0,
                processing_time=processing_time,
                angle_validations=angle_validations,
                embeddings_stored=0,
                error=f"Only {len(valid_embeddings)}/3 embeddings could be extracted. Ensure face is clearly visible in all captures.",
            )
        
        # Store all embeddings
        storage_errors = []
        for emb_data in valid_embeddings:
            result = face_recognizer.register_person_embedding(
                request.person_id, 
                emb_data["embedding"],
                angle=emb_data["angle"],
            )
            if result.get("success"):
                embeddings_stored += 1
                logger.info(f"Stored {emb_data['angle']} embedding for {request.person_id}")
            else:
                error = result.get("error", "Unknown error")
                logger.error(f"Failed to store {emb_data['angle']} embedding: {error}")
                storage_errors.append(f"{emb_data['angle']}: {error}")
        
        processing_time = time.time() - start_time
        
        if embeddings_stored >= 3:
            return MultiAngleRegistrationResponse(
                success=True,
                person_id=request.person_id,
                total_persons=face_recognizer.get_person_count(),
                processing_time=processing_time,
                angle_validations=angle_validations,
                embeddings_stored=embeddings_stored,
            )
        else:
            error_detail = "; ".join(storage_errors) if storage_errors else "Database storage failed"
            return MultiAngleRegistrationResponse(
                success=False,
                person_id=request.person_id,
                total_persons=0,
                processing_time=processing_time,
                angle_validations=angle_validations,
                embeddings_stored=embeddings_stored,
                error=f"Only {embeddings_stored}/3 embeddings could be stored. {error_detail}",
            )
        
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Multi-angle registration error: {e}")
        return MultiAngleRegistrationResponse(
            success=False,
            person_id=request.person_id,
            total_persons=0,
            processing_time=processing_time,
            angle_validations=angle_validations,
            embeddings_stored=embeddings_stored,
            error=str(e),
        )
