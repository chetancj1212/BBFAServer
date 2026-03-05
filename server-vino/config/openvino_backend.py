"""
OpenVINO Inference Wrapper
==========================
Drop-in replacement for onnxruntime.InferenceSession using OpenVINO natively.
Falls back to onnxruntime if OpenVINO is not available.

OpenVINO can load ONNX models directly and provides hardware acceleration
on Intel CPUs, iGPUs, and NPUs without needing onnxruntime-openvino.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Detect OpenVINO availability
OPENVINO_AVAILABLE = False
OPENVINO_DEVICES = []

try:
    from openvino import Core, Tensor as OVTensor
    _core = Core()
    OPENVINO_DEVICES = _core.available_devices
    OPENVINO_AVAILABLE = True
    logger.info(f"OpenVINO available. Devices: {OPENVINO_DEVICES}")
except ImportError:
    logger.info("OpenVINO not available, will use onnxruntime")


def _partial_shape_to_list(partial_shape):
    """Convert OpenVINO PartialShape to list of ints (or -1 for dynamic dims)."""
    result = []
    for dim in partial_shape:
        if dim.is_static:
            result.append(dim.get_length())
        else:
            result.append(-1)  # dynamic dimension
    return result


class _InputMeta:
    """Mimics onnxruntime input metadata."""
    def __init__(self, name, shape):
        self.name = name
        self.shape = shape


class _OutputMeta:
    """Mimics onnxruntime output metadata."""
    def __init__(self, name, shape):
        self.name = name
        self.shape = shape


class OpenVINOSession:
    """
    Drop-in replacement for ort.InferenceSession using OpenVINO.
    
    Supports the same API:
        session.run(output_names, {input_name: input_data})
        session.get_inputs()
        session.get_outputs()
        session.get_providers()
    """

    def __init__(self, model_path: str, device: str = "AUTO"):
        """
        Load an ONNX model with OpenVINO.

        Args:
            model_path: Path to the .onnx model file
            device: OpenVINO device string ("CPU", "GPU", "AUTO", etc.)
        """
        self.model_path = model_path
        self.device = device

        core = Core()
        self.model = core.read_model(model=str(model_path))
        self.compiled = core.compile_model(self.model, device_name=device)
        self.infer_request = self.compiled.create_infer_request()

        # Cache input/output metadata (convert Dimensions to plain ints)
        self._inputs = []
        for inp in self.model.inputs:
            name = inp.any_name
            shape = _partial_shape_to_list(inp.partial_shape)
            self._inputs.append(_InputMeta(name, shape))

        self._outputs = []
        for out in self.model.outputs:
            name = out.any_name
            shape = _partial_shape_to_list(out.partial_shape)
            self._outputs.append(_OutputMeta(name, shape))

        logger.info(
            f"OpenVINO session created: {model_path} on device={device}"
        )

    def get_inputs(self):
        return self._inputs

    def get_outputs(self):
        return self._outputs

    def get_providers(self):
        return [f"OpenVINOExecutionProvider ({self.device})"]

    def run(self, output_names, input_feed: Dict[str, np.ndarray], **kwargs):
        """
        Run inference. Compatible with ort.InferenceSession.run().

        Args:
            output_names: List of output names or None for all outputs
            input_feed: Dict mapping input name -> numpy array

        Returns:
            List of numpy arrays, one per output
        """
        # Set inputs — wrap numpy arrays in OpenVINO Tensor objects
        for name, data in input_feed.items():
            ov_tensor = OVTensor(np.ascontiguousarray(data))
            self.infer_request.set_tensor(name, ov_tensor)

        self.infer_request.infer()

        # Gather outputs as numpy arrays (matches onnxruntime output format)
        # NOTE: onnxruntime treats [] same as None (return all outputs)
        results = []
        if output_names is None or len(output_names) == 0:
            for i in range(len(self._outputs)):
                tensor = self.infer_request.get_output_tensor(i)
                results.append(np.array(tensor.data, copy=True))
        else:
            for name in output_names:
                tensor = self.infer_request.get_tensor(name)
                results.append(np.array(tensor.data, copy=True))

        return results


def create_session(
    model_path: str,
    device: str = "AUTO",
    prefer_openvino: bool = True,
    ort_providers=None,
    ort_session_options=None,
):
    """
    Create an inference session, preferring OpenVINO if available.

    Returns an object with the same API as ort.InferenceSession:
        .run(), .get_inputs(), .get_outputs(), .get_providers()

    Args:
        model_path: Path to ONNX model
        device: OpenVINO device ("AUTO", "CPU", "GPU")
        prefer_openvino: If True, try OpenVINO first
        ort_providers: Fallback onnxruntime providers
        ort_session_options: Fallback onnxruntime session options dict

    Returns:
        Session object (OpenVINOSession or ort.InferenceSession)
    """
    if prefer_openvino and OPENVINO_AVAILABLE:
        try:
            session = OpenVINOSession(model_path, device=device)
            return session
        except Exception as e:
            logger.warning(f"OpenVINO failed for {model_path}: {e}, falling back to onnxruntime")

    # Fallback to onnxruntime
    import onnxruntime as ort

    providers = ort_providers or ["CPUExecutionProvider"]

    sess_opts = ort.SessionOptions()
    sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_opts.intra_op_num_threads = 0
    sess_opts.inter_op_num_threads = 0

    if ort_session_options:
        for key, value in ort_session_options.items():
            if hasattr(sess_opts, key):
                setattr(sess_opts, key, value)

    session = ort.InferenceSession(
        str(model_path), sess_options=sess_opts, providers=providers
    )
    return session
