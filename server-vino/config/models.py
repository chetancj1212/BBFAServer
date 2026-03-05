from .paths import WEIGHTS_DIR, DATA_DIR
from .onnx import OPTIMIZED_PROVIDERS, OPTIMIZED_SESSION_OPTIONS

# =============================================================================
# MODEL CONFIGURATION (Jan 2026)
# =============================================================================
# Detector: SCRFD-10G (4m range, multi-face)
# Recognizer: ArcFace/Buffalo_L (99.83% LFW accuracy)
# Liveness: 128x128 binary classifier
# =============================================================================

MODEL_CONFIGS = {
    "face_detector": {
        "model_path": WEIGHTS_DIR / "scrfd_10g.onnx",
        "scrfd_model_path": WEIGHTS_DIR / "scrfd_10g.onnx",
        "input_size": (640, 640),
        "score_threshold": 0.30,
        "nms_threshold": 0.4,
        "top_k": 5000,
        "min_face_size": 16,
        "edge_margin": 3,
    },
    "liveness_detector": {
        "model_path": WEIGHTS_DIR / "liveness.onnx",
        "confidence_threshold": 0.4,
        "bbox_inc": 1.2,
        "model_img_size": 128,
        "temporal_alpha": 0.35,
        "enable_temporal_smoothing": True,
    },
    "face_recognizer": {
        "model_path": WEIGHTS_DIR / "recognizer.onnx",
        "input_size": (112, 112),
        "similarity_threshold": 0.35,  # Slightly lower for distant faces
        "providers": OPTIMIZED_PROVIDERS,
        "session_options": OPTIMIZED_SESSION_OPTIONS,
        "embedding_dimension": 512,
        "database_path": DATA_DIR / "face_database.db",
        # Distance enhancement settings
        "small_face_threshold": 80,  # Faces smaller than this get super-resolution
        "upscale_target_size": 160,  # Target size after upscaling
    },
}

FACE_DETECTOR_MODEL_PATH = MODEL_CONFIGS["face_detector"]["model_path"]
FACE_DETECTOR_CONFIG = MODEL_CONFIGS["face_detector"]
LIVENESS_DETECTOR_CONFIG = MODEL_CONFIGS["liveness_detector"]
FACE_RECOGNIZER_MODEL_PATH = MODEL_CONFIGS["face_recognizer"]["model_path"]
FACE_RECOGNIZER_CONFIG = MODEL_CONFIGS["face_recognizer"]


def validate_model_paths():
    missing_models = []
    for model_name, model_config in MODEL_CONFIGS.items():
        if "model_path" not in model_config:
            continue
        model_path = model_config["model_path"]
        if not model_path.exists():
            missing_models.append(f"{model_name}: {model_path}")
    if missing_models:
        raise FileNotFoundError("Missing model files:\n" + "\n".join(missing_models))


def validate_directories():
    from .paths import WEIGHTS_DIR, BASE_DIR

    required_dirs = [
        WEIGHTS_DIR,
        BASE_DIR.parent / "core" / "models",
        BASE_DIR.parent / "utils",
    ]
    for directory in required_dirs:
        directory.mkdir(parents=True, exist_ok=True)
