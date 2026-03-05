# Face Detector - SCRFD
from .face_detector.scrfd_detector import SCRFDDetector as FaceDetector

# Liveness Detector
from .liveness_detector.detector import LivenessDetector

# Face Recognizer - ArcFace
from .face_recognizer.arcface_recognizer import ArcFaceRecognizer as FaceRecognizer


__all__ = ["FaceDetector", "LivenessDetector", "FaceRecognizer"]
