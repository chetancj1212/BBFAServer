import os
import logging
from typing import Tuple, Optional, List, Dict, Any

logger = logging.getLogger(__name__)


def init_onnx_session(
    model_path: str,
    providers: Optional[List] = None,
    session_options: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[object], Optional[str]]:
    """Initialize inference session using OpenVINO or onnxruntime fallback."""
    if not os.path.isfile(model_path):
        return None, None

    # Try OpenVINO native backend first
    try:
        try:
            from config.openvino_backend import create_session
        except ImportError:
            from server.config.openvino_backend import create_session
        session = create_session(model_path)
        input_name = session.get_inputs()[0].name
        logger.info(f"Liveness active providers: {session.get_providers()}")
        return session, input_name
    except (ImportError, Exception) as e:
        logger.warning(f"OpenVINO backend unavailable for liveness: {e}, using onnxruntime")

    # Fallback to onnxruntime
    import onnxruntime as ort

    if providers is None:
        providers = ["CPUExecutionProvider"]

    sess_opts = None
    if session_options is None:
        try:
            try:
                from config.onnx import OPTIMIZED_SESSION_OPTIONS
            except ImportError:
                from server.config.onnx import OPTIMIZED_SESSION_OPTIONS
            sess_opts = ort.SessionOptions()
            for key, value in OPTIMIZED_SESSION_OPTIONS.items():
                if hasattr(sess_opts, key):
                    setattr(sess_opts, key, value)
        except (ImportError, AttributeError):
            pass

    try:
        if sess_opts:
            ort_session = ort.InferenceSession(
                model_path, sess_options=sess_opts, providers=providers
            )
        else:
            ort_session = ort.InferenceSession(model_path, providers=providers)
    except Exception:
        try:
            ort_session = ort.InferenceSession(
                model_path, providers=["CPUExecutionProvider"]
            )
        except Exception:
            return None, None

    input_name = None
    if ort_session:
        input_name = ort_session.get_inputs()[0].name
        logger.info(f"Liveness active providers: {ort_session.get_providers()}")

    return ort_session, input_name
