import os
import logging
from typing import Tuple, Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def init_face_recognizer_session(
    model_path: str,
    providers: Optional[List[str]] = None,
    session_options: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[object], Optional[str]]:
    """
    Initialize face recognition session using OpenVINO or onnxruntime fallback.

    Args:
        model_path: Path to ONNX model file
        providers: List of execution providers (fallback only)
        session_options: Optional session configuration options (fallback only)

    Returns:
        Tuple of (session, input_name)
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")

    # Try OpenVINO native backend first
    try:
        try:
            from config.openvino_backend import create_session
        except ImportError:
            from server.config.openvino_backend import create_session
        session = create_session(model_path)
        input_name = session.get_inputs()[0].name
        logger.info(f"Face recognizer model loaded from {model_path}")
        logger.info(f"Face recognizer active providers: {session.get_providers()}")
        return session, input_name
    except (ImportError, Exception) as e:
        logger.warning(f"OpenVINO backend unavailable for recognizer: {e}, using onnxruntime")

    # Fallback to onnxruntime
    import onnxruntime as ort

    providers = providers or ["CPUExecutionProvider"]

    try:
        ort_opts = ort.SessionOptions()

        if session_options:
            for key, value in session_options.items():
                if hasattr(ort_opts, key):
                    setattr(ort_opts, key, value)

        session = ort.InferenceSession(
            model_path, sess_options=ort_opts, providers=providers
        )

        input_name = session.get_inputs()[0].name

        logger.info(f"Face recognizer model loaded from {model_path}")
        logger.info(f"Face recognizer active providers: {session.get_providers()}")
        return session, input_name

    except Exception as e:
        logger.error(f"Failed to initialize face recognizer model: {e}")
        raise
