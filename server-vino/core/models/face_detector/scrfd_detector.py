"""
SCRFD Face Detector
====================
High-accuracy face detector using SCRFD-10G model from InsightFace.

SCRFD (Sample and Computation Redistribution for Efficient Face Detection)
provides state-of-the-art accuracy while maintaining high speed.

Model: SCRFD-10G (10 GFLOPs) - best balance of speed and accuracy
Input: 640x640 (configurable)
Output: Face bounding boxes + 5 landmarks

Reference: https://github.com/deepinsight/insightface/tree/master/detection/scrfd
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

try:
    import onnxruntime as ort
except ImportError:
    raise ImportError("onnxruntime is required for SCRFD detector")

logger = logging.getLogger(__name__)


class SCRFDDetector:
    """
    SCRFD face detector using ONNX Runtime.
    
    Features:
    - Multi-scale detection (8, 16, 32 strides)
    - 5-point facial landmarks
    - High accuracy (99.5%+ on WiderFace)
    - Supports CPU inference
    """
    
    def __init__(
        self,
        model_path: str,
        input_size: Tuple[int, int] = (640, 640),
        conf_threshold: float = 0.5,
        nms_threshold: float = 0.4,
    ):
        """
        Initialize SCRFD detector.
        
        Args:
            model_path: Path to SCRFD ONNX model
            input_size: Model input size (width, height)
            conf_threshold: Confidence threshold for detections
            nms_threshold: NMS IoU threshold
        """
        self.model_path = Path(model_path)
        self.input_size = input_size  # (width, height)
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        
        # Validate model exists
        if not self.model_path.exists():
            raise FileNotFoundError(f"SCRFD model not found: {model_path}")
        
        # Initialize ONNX Runtime session
        self._init_session()
        
        # SCRFD-10G uses strides 8, 16, 32
        self._feat_stride_fpn = [8, 16, 32]
        
        # Number of anchors per position (SCRFD uses 2 anchors)
        self.num_anchors = 2
        
        # Generate anchor centers for all strides
        self._generate_anchors()
        
        logger.info(
            f"SCRFD initialized: {input_size}, "
            f"conf={conf_threshold}, nms={nms_threshold}"
        )
    
    def _init_session(self):
        """Initialize inference session with OpenVINO or onnxruntime fallback."""
        try:
            try:
                from config.openvino_backend import create_session
            except ImportError:
                from server.config.openvino_backend import create_session
            self.session = create_session(str(self.model_path))
        except (ImportError, Exception) as e:
            logger.warning(f"OpenVINO backend unavailable: {e}, using onnxruntime")
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 0
            sess_options.inter_op_num_threads = 0
            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=sess_options,
                providers=['CPUExecutionProvider'],
            )
        
        # Log which provider is actually being used
        active_providers = self.session.get_providers()
        logger.info(f"SCRFD active providers: {active_providers}")
        
        # Get input/output info
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        
        # SCRFD-10G outputs: 9 total (3 scores + 3 bbox + 3 kps)
        num_outputs = len(self.output_names)
        self.use_kps = num_outputs >= 9
        
        logger.info(f"SCRFD outputs: {num_outputs}, use_kps: {self.use_kps}")
    
    def _generate_anchors(self):
        """Generate anchor centers for all feature map strides."""
        input_height, input_width = self.input_size[1], self.input_size[0]
        
        self.anchor_centers = {}
        
        for stride in self._feat_stride_fpn:
            height = input_height // stride
            width = input_width // stride
            
            # Generate grid
            shift_x = (np.arange(0, width) + 0.5) * stride
            shift_y = (np.arange(0, height) + 0.5) * stride
            
            shift_x, shift_y = np.meshgrid(shift_x, shift_y)
            centers = np.stack([shift_x.ravel(), shift_y.ravel()], axis=-1)
            
            # Repeat for num_anchors
            centers = np.tile(centers, (1, self.num_anchors)).reshape(-1, 2)
            
            self.anchor_centers[stride] = centers.astype(np.float32)
    
    def detect_faces(self, image: np.ndarray, enable_liveness: bool = False) -> List[Dict]:
        """
        Detect faces in an image.
        
        Args:
            image: BGR image (numpy array)
            enable_liveness: Flag for liveness processing (affects filtering)
            
        Returns:
            List of face detections with bbox, confidence, and landmarks_5
        """
        if image is None or image.size == 0:
            logger.warning("Invalid image provided to SCRFD detector")
            return []
        
        orig_height, orig_width = image.shape[:2]
        
        # Preprocess
        input_tensor, det_scale = self._preprocess(image)
        
        # Run inference
        try:
            outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
        except Exception as e:
            logger.error(f"SCRFD inference failed: {e}")
            return []
        
        # Postprocess
        detections = self._postprocess(outputs, det_scale, orig_width, orig_height)
        
        return detections
    
    def _preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Preprocess image for SCRFD.
        
        Args:
            image: BGR image
            
        Returns:
            Preprocessed tensor, detection scale
        """
        input_width, input_height = self.input_size
        
        # Resize with aspect ratio preservation
        im_ratio = image.shape[0] / image.shape[1]
        model_ratio = input_height / input_width
        
        if im_ratio > model_ratio:
            new_height = input_height
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_width
            new_height = int(new_width * im_ratio)
        
        det_scale = new_height / image.shape[0]
        
        resized = cv2.resize(image, (new_width, new_height))
        
        # Create padded image
        det_img = np.zeros((input_height, input_width, 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized
        
        # Convert BGR to RGB and normalize
        det_img = cv2.cvtColor(det_img, cv2.COLOR_BGR2RGB)
        det_img = det_img.astype(np.float32)
        
        # Standard ImageNet normalization
        det_img = (det_img - 127.5) / 128.0
        
        # HWC -> CHW -> NCHW
        det_img = det_img.transpose(2, 0, 1)
        det_img = np.expand_dims(det_img, axis=0)
        
        return det_img, det_scale
    
    def _postprocess(
        self,
        outputs: List[np.ndarray],
        det_scale: float,
        orig_width: int,
        orig_height: int,
    ) -> List[Dict]:
        """
        Postprocess SCRFD outputs.
        
        SCRFD-10G output format (9 outputs):
        - outputs[0-2]: scores for stride 8, 16, 32 (shape: [N, 1])
        - outputs[3-5]: bbox for stride 8, 16, 32 (shape: [N, 4])
        - outputs[6-8]: kps for stride 8, 16, 32 (shape: [N, 10])
        """
        scores_list = []
        bboxes_list = []
        kpss_list = []
        
        fmc = len(self._feat_stride_fpn)
        
        for idx, stride in enumerate(self._feat_stride_fpn):
            # Get outputs for this stride
            scores = outputs[idx]           # [N, 1]
            bbox_preds = outputs[fmc + idx] # [N, 4]
            
            if self.use_kps:
                kps_preds = outputs[fmc * 2 + idx]  # [N, 10]
            else:
                kps_preds = None
            
            anchor_centers = self.anchor_centers[stride]
            
            # Flatten scores
            scores = scores.reshape(-1)
            
            # Filter by confidence threshold first (for efficiency)
            pos_inds = np.where(scores >= self.conf_threshold)[0]
            
            if len(pos_inds) == 0:
                continue
            
            # Get positive samples
            pos_scores = scores[pos_inds]
            pos_bbox_preds = bbox_preds[pos_inds]
            pos_anchors = anchor_centers[pos_inds]
            
            # Decode bboxes: distance to xyxy
            bboxes = self._distance2bbox(pos_anchors, pos_bbox_preds, stride)
            
            scores_list.append(pos_scores)
            bboxes_list.append(bboxes)
            
            # Decode keypoints
            if kps_preds is not None:
                pos_kps_preds = kps_preds[pos_inds]
                kpss = self._distance2kps(pos_anchors, pos_kps_preds, stride)
                kpss_list.append(kpss)
        
        # If no detections, return empty
        if len(scores_list) == 0:
            return []
        
        # Concatenate all scales
        scores = np.concatenate(scores_list)
        bboxes = np.concatenate(bboxes_list)
        
        if len(kpss_list) > 0:
            kpss = np.concatenate(kpss_list)
        else:
            kpss = None
        
        # Apply NMS
        keep = self._nms(bboxes, scores, self.nms_threshold)
        
        # Build final detections
        detections = []
        for i in keep:
            # Scale back to original image coordinates
            bbox = bboxes[i] / det_scale
            
            # Clip to image boundaries
            x1 = max(0, min(bbox[0], orig_width - 1))
            y1 = max(0, min(bbox[1], orig_height - 1))
            x2 = max(0, min(bbox[2], orig_width - 1))
            y2 = max(0, min(bbox[3], orig_height - 1))
            
            # Skip invalid boxes
            if x2 <= x1 or y2 <= y1:
                continue
            
            detection = {
                "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)],  # [x, y, w, h]
                "confidence": float(scores[i]),
            }
            
            # Add landmarks if available
            if kpss is not None:
                kps = kpss[i] / det_scale
                # Reshape to 5x2
                landmarks = kps.reshape(5, 2).tolist()
                detection["landmarks_5"] = landmarks
            
            detections.append(detection)
        
        return detections
    
    def _distance2bbox(
        self,
        points: np.ndarray,
        distance: np.ndarray,
        stride: int,
    ) -> np.ndarray:
        """Convert distance predictions to bounding boxes."""
        distance = distance * stride
        
        x1 = points[:, 0] - distance[:, 0]
        y1 = points[:, 1] - distance[:, 1]
        x2 = points[:, 0] + distance[:, 2]
        y2 = points[:, 1] + distance[:, 3]
        
        return np.stack([x1, y1, x2, y2], axis=-1)
    
    def _distance2kps(
        self,
        points: np.ndarray,
        distance: np.ndarray,
        stride: int,
    ) -> np.ndarray:
        """Convert distance predictions to keypoints."""
        distance = distance * stride
        
        kps = np.zeros((distance.shape[0], 10), dtype=np.float32)
        
        for i in range(5):
            kps[:, i * 2] = points[:, 0] + distance[:, i * 2]
            kps[:, i * 2 + 1] = points[:, 1] + distance[:, i * 2 + 1]
        
        return kps
    
    def _nms(
        self,
        bboxes: np.ndarray,
        scores: np.ndarray,
        threshold: float,
    ) -> List[int]:
        """Non-Maximum Suppression."""
        x1 = bboxes[:, 0]
        y1 = bboxes[:, 1]
        x2 = bboxes[:, 2]
        y2 = bboxes[:, 3]
        
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]
        
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            
            if order.size == 1:
                break
            
            # Compute IoU with rest
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            
            w = np.maximum(0.0, xx2 - xx1)
            h = np.maximum(0.0, yy2 - yy1)
            
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter)
            
            # Keep boxes with IoU below threshold
            inds = np.where(iou <= threshold)[0]
            order = order[inds + 1]
        
        return keep
    
    # -------------------------------------------------------------------------
    # Compatibility methods (same interface as YuNet detector)
    # -------------------------------------------------------------------------
    
    def get_face_count(self, image: np.ndarray) -> int:
        """Get the number of detected faces."""
        faces = self.detect_faces(image)
        return len(faces)
    
    def detect_and_get_largest(
        self,
        image: np.ndarray,
        enable_liveness: bool = False,
    ) -> Optional[Dict]:
        """Detect faces and return the largest one."""
        faces = self.detect_faces(image, enable_liveness=enable_liveness)
        
        if not faces:
            return None
        
        # Find largest by area
        largest = max(faces, key=lambda f: f["bbox"][2] * f["bbox"][3])
        return largest
    
    def set_input_size(self, size: Tuple[int, int]):
        """Update input size and regenerate anchors."""
        if size != self.input_size:
            self.input_size = size
            self._generate_anchors()
            logger.info(f"SCRFD input size updated to {size}")

    def set_confidence_threshold(self, threshold: float):
        """Update confidence threshold."""
        self.conf_threshold = threshold

    def set_nms_threshold(self, threshold: float):
        """Update NMS threshold."""
        self.nms_threshold = threshold

    def set_min_face_size(self, min_size: int):
        """Update minimum face size (for compatibility, not used in SCRFD)."""
        # SCRFD handles this differently via confidence threshold
        # Lower confidence for smaller faces
        pass
