import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config.paths import DATA_DIR
from config.models import (
    FACE_DETECTOR_CONFIG,
    FACE_DETECTOR_MODEL_PATH,
    FACE_RECOGNIZER_CONFIG,
    FACE_RECOGNIZER_MODEL_PATH,
    LIVENESS_DETECTOR_CONFIG,
)
from core.models import (
    LivenessDetector,
    FaceDetector,
    FaceRecognizer,
)
from database.attendance import AttendanceDatabaseManager
from database.history import AttendanceHistoryManager
from hooks import set_model_references

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _init_face_detector():
    """Initialize SCRFD face detector."""
    from core.models.face_detector.scrfd_detector import SCRFDDetector
    
    scrfd_model_path = FACE_DETECTOR_CONFIG.get("scrfd_model_path")
    if scrfd_model_path is None:
        scrfd_model_path = FACE_DETECTOR_MODEL_PATH
    
    logger.info(f"Initializing SCRFD face detector from {scrfd_model_path}...")
    return SCRFDDetector(
        model_path=str(scrfd_model_path),
        input_size=FACE_DETECTOR_CONFIG["input_size"],
        conf_threshold=FACE_DETECTOR_CONFIG["score_threshold"],
        nms_threshold=FACE_DETECTOR_CONFIG["nms_threshold"],
    )


def _init_liveness_detector():
    """Initialize liveness detector."""
    from core.models.liveness_detector.detector import LivenessDetector
    
    logger.info("Initializing liveness detector...")
    return LivenessDetector(
        model_path=str(LIVENESS_DETECTOR_CONFIG["model_path"]),
        model_img_size=LIVENESS_DETECTOR_CONFIG["model_img_size"],
        confidence_threshold=LIVENESS_DETECTOR_CONFIG["confidence_threshold"],
        bbox_inc=LIVENESS_DETECTOR_CONFIG["bbox_inc"],
        temporal_alpha=LIVENESS_DETECTOR_CONFIG["temporal_alpha"],
        enable_temporal_smoothing=LIVENESS_DETECTOR_CONFIG["enable_temporal_smoothing"],
    )


def _init_face_recognizer():
    """Initialize ArcFace recognizer."""
    from core.models.face_recognizer.arcface_recognizer import ArcFaceRecognizer
    
    logger.info("Initializing ArcFace recognizer...")
    return ArcFaceRecognizer(
        model_path=str(FACE_RECOGNIZER_MODEL_PATH),
        input_size=FACE_RECOGNIZER_CONFIG["input_size"],
        similarity_threshold=FACE_RECOGNIZER_CONFIG["similarity_threshold"],
        providers=FACE_RECOGNIZER_CONFIG["providers"],
        database_path=str(FACE_RECOGNIZER_CONFIG["database_path"]),
        session_options=FACE_RECOGNIZER_CONFIG["session_options"],
        embedding_dimension=FACE_RECOGNIZER_CONFIG["embedding_dimension"],
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting up backend server...")
        logger.info("=" * 60)
        logger.info("Model Upgrade Status (Jan 2026):")
        logger.info("  - Detector: SCRFD-10G (4m range, multi-face)")
        logger.info("  - Recognizer: ArcFace/Buffalo_L (99.83% LFW)")
        logger.info("  - Liveness: MiniFASNetV2 (multi-scale)")
        logger.info("=" * 60)

        # Check if models need to be downloaded
        try:
            from utils.model_downloader import verify_models, download_all_models
            verification = verify_models()
            missing = [k for k, v in verification.items() if not v]
            
            if missing:
                logger.warning(f"Missing models detected: {missing}")
                logger.info("Attempting to download missing models...")
                download_all_models()
        except Exception as e:
            logger.warning(f"Model verification skipped: {e}")

        # Initialize models
        fd = _init_face_detector()
        ld = _init_liveness_detector()
        fr = _init_face_recognizer()

        att_db = AttendanceDatabaseManager(str(DATA_DIR / "attendance.db"))
        hist_db = AttendanceHistoryManager(str(DATA_DIR / "attendance_history.db"))

        # ── Store everything on app.state (Fix #6) ──
        app.state.face_detector = fd
        app.state.liveness_detector = ld
        app.state.face_recognizer = fr
        app.state.attendance_db = att_db
        app.state.history_db = hist_db
        app.state.face_db = fr.db_manager if fr else None

        # ── Concurrency controls (Scalability Fixes #1 & #2) ──
        max_concurrent = int(os.environ.get("MAX_INFERENCE_CONCURRENCY", "4"))
        app.state.inference_semaphore = asyncio.Semaphore(max_concurrent)
        app.state.thread_pool = ThreadPoolExecutor(
            max_workers=max_concurrent,
            thread_name_prefix="ai-inference",
        )
        logger.info(f"Inference concurrency: max {max_concurrent} simultaneous")

        # Set globally for legacy hooks (process_face_detection, etc.)
        set_model_references(ld, None, fr, fd)
        
        logger.info("Startup complete")

    except Exception as e:
        logger.error(f"Failed to initialize models: {e}")
        raise

    yield

    logger.info("Shutting down...")
    # Clean up thread pool
    pool = getattr(app.state, "thread_pool", None)
    if pool:
        pool.shutdown(wait=False)
    logger.info("Shutdown complete")
