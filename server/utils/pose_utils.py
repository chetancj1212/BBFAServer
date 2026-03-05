"""
Face Pose Estimation Utilities

Estimates head pose (yaw, pitch, roll) from 5-point facial landmarks.
Used to validate face angle during registration and filter extreme angles during recognition.

Landmark indices (5-point):
    [0] Left Eye
    [1] Right Eye
    [2] Nose tip
    [3] Left Mouth corner
    [4] Right Mouth corner
"""

import numpy as np
from typing import Tuple, Dict, Optional, List, Any
import logging

logger = logging.getLogger(__name__)


# Angle thresholds for different quality levels
ANGLE_THRESHOLDS = {
    "frontal": 15.0,      # 0-15° is considered frontal
    "acceptable": 30.0,   # 15-30° is acceptable for registration
    "recognition": 45.0,  # Up to 45° can be recognized
    "extreme": 60.0,      # Beyond 60° is unreliable
}


def estimate_yaw_angle(landmarks_5: np.ndarray) -> float:
    """
    Estimate yaw angle (left-right rotation) from 5-point landmarks.
    
    Uses nose position relative to eye midpoint as primary signal.
    
    Args:
        landmarks_5: 5-point landmarks array of shape (5, 2)
        
    Returns:
        Yaw angle in degrees (-90 to +90)
        Negative = looking right, Positive = looking left
    """
    landmarks = np.array(landmarks_5, dtype=np.float32)
    
    if landmarks.shape != (5, 2):
        raise ValueError(f"Expected landmarks shape (5, 2), got {landmarks.shape}")
    
    left_eye = landmarks[0]
    right_eye = landmarks[1]
    nose = landmarks[2]
    
    # Eye center and width
    eye_center_x = (left_eye[0] + right_eye[0]) / 2
    eye_width = abs(right_eye[0] - left_eye[0])
    
    if eye_width < 1:
        logger.warning("Eye width too small for angle estimation")
        return 0.0
    
    # Nose offset from eye center, normalized by eye width
    nose_offset = (nose[0] - eye_center_x) / eye_width
    
    # Convert to approximate angle
    # Empirically: nose_offset of ~0.5 corresponds to ~45°
    yaw_angle = nose_offset * 90.0
    
    # Clamp to reasonable range
    yaw_angle = max(-90.0, min(90.0, yaw_angle))
    
    return float(yaw_angle)


def estimate_pitch_angle(landmarks_5: np.ndarray) -> float:
    """
    Estimate pitch angle (up-down tilt) from 5-point landmarks.
    
    Uses vertical distance ratios between eyes, nose, and mouth.
    
    Args:
        landmarks_5: 5-point landmarks array of shape (5, 2)
        
    Returns:
        Pitch angle in degrees (-45 to +45)
        Negative = looking down, Positive = looking up
    """
    landmarks = np.array(landmarks_5, dtype=np.float32)
    
    if landmarks.shape != (5, 2):
        raise ValueError(f"Expected landmarks shape (5, 2), got {landmarks.shape}")
    
    left_eye = landmarks[0]
    right_eye = landmarks[1]
    nose = landmarks[2]
    left_mouth = landmarks[3]
    right_mouth = landmarks[4]
    
    # Eye center Y position
    eye_center_y = (left_eye[1] + right_eye[1]) / 2
    
    # Mouth center Y position
    mouth_center_y = (left_mouth[1] + right_mouth[1]) / 2
    
    # Distance from eyes to nose
    eye_to_nose = nose[1] - eye_center_y
    
    # Distance from nose to mouth
    nose_to_mouth = mouth_center_y - nose[1]
    
    # Total face height (eyes to mouth)
    face_height = mouth_center_y - eye_center_y
    
    if face_height < 1:
        return 0.0
    
    # Ratio of eye-to-nose vs total face height
    # For frontal face, this is typically ~0.45
    # Looking up: ratio decreases (nose appears higher relative to face)
    # Looking down: ratio increases (nose appears lower)
    ratio = eye_to_nose / face_height
    
    # Empirical conversion (0.45 is neutral, varies ~0.1 for ±30°)
    pitch_angle = (ratio - 0.45) * 200.0
    
    # Clamp to reasonable range
    pitch_angle = max(-45.0, min(45.0, pitch_angle))
    
    return float(pitch_angle)


def estimate_roll_angle(landmarks_5: np.ndarray) -> float:
    """
    Estimate roll angle (head tilt) from 5-point landmarks.
    
    Uses angle of line connecting the two eyes.
    
    Args:
        landmarks_5: 5-point landmarks array of shape (5, 2)
        
    Returns:
        Roll angle in degrees (-45 to +45)
        Negative = tilted right, Positive = tilted left
    """
    landmarks = np.array(landmarks_5, dtype=np.float32)
    
    if landmarks.shape != (5, 2):
        raise ValueError(f"Expected landmarks shape (5, 2), got {landmarks.shape}")
    
    left_eye = landmarks[0]
    right_eye = landmarks[1]
    
    # Angle of eye line
    dx = right_eye[0] - left_eye[0]
    dy = right_eye[1] - left_eye[1]
    
    if abs(dx) < 1:
        return 0.0
    
    roll_angle = np.degrees(np.arctan2(dy, dx))
    
    # Clamp to reasonable range
    roll_angle = max(-45.0, min(45.0, roll_angle))
    
    return float(roll_angle)


def estimate_face_pose(landmarks_5: np.ndarray) -> Dict[str, float]:
    """
    Estimate complete face pose from 5-point landmarks.
    
    Args:
        landmarks_5: 5-point landmarks array of shape (5, 2)
        
    Returns:
        Dictionary with yaw, pitch, roll angles in degrees
    """
    landmarks = np.array(landmarks_5, dtype=np.float32)
    
    try:
        yaw = estimate_yaw_angle(landmarks)
        pitch = estimate_pitch_angle(landmarks)
        roll = estimate_roll_angle(landmarks)
        
        return {
            "yaw": yaw,
            "pitch": pitch,
            "roll": roll,
            "abs_yaw": abs(yaw),
            "abs_pitch": abs(pitch),
            "abs_roll": abs(roll),
        }
    except Exception as e:
        logger.error(f"Pose estimation failed: {e}")
        return {
            "yaw": 0.0,
            "pitch": 0.0,
            "roll": 0.0,
            "abs_yaw": 0.0,
            "abs_pitch": 0.0,
            "abs_roll": 0.0,
        }


def classify_face_angle(
    landmarks_5: np.ndarray,
    expected_angle: str = "front"
) -> Dict[str, Any]:
    """
    Classify face angle and check if it matches expected pose.
    
    Args:
        landmarks_5: 5-point landmarks
        expected_angle: Expected pose ("front", "left", "right")
        
    Returns:
        Dictionary with:
            - is_valid: Whether the pose matches expected
            - pose: Pose estimation dict
            - direction: Detected direction
            - error: Error message if invalid
    """
    pose = estimate_face_pose(landmarks_5)
    yaw = pose["yaw"]
    abs_yaw = pose["abs_yaw"]
    
    # Determine detected direction
    if abs_yaw < ANGLE_THRESHOLDS["frontal"]:
        direction = "front"
    elif yaw > 0:
        direction = "left"
    else:
        direction = "right"
    
    result = {
        "pose": pose,
        "direction": direction,
        "expected": expected_angle,
        "is_valid": False,
        "error": None,
    }
    
    if expected_angle == "front":
        if abs_yaw <= ANGLE_THRESHOLDS["frontal"]:
            result["is_valid"] = True
        elif abs_yaw <= ANGLE_THRESHOLDS["acceptable"]:
            result["is_valid"] = True  # Acceptable but not ideal
            result["warning"] = "Slightly angled, frontal preferred"
        else:
            result["error"] = f"Face too angled ({abs_yaw:.0f}°). Please look directly at camera."
            
    elif expected_angle == "left":
        # For left profile, expect yaw between 20-40°
        if 15 <= yaw <= 45:
            result["is_valid"] = True
        elif yaw > 45:
            result["error"] = f"Too much left turn ({yaw:.0f}°). Turn slightly toward camera."
        elif yaw < 15:
            result["error"] = f"Not enough left turn ({yaw:.0f}°). Turn your head left ~30°."
            
    elif expected_angle == "right":
        # For right profile, expect yaw between -20 to -40°
        if -45 <= yaw <= -15:
            result["is_valid"] = True
        elif yaw < -45:
            result["error"] = f"Too much right turn ({abs(yaw):.0f}°). Turn slightly toward camera."
        elif yaw > -15:
            result["error"] = f"Not enough right turn ({abs(yaw):.0f}°). Turn your head right ~30°."
    
    return result


def is_angle_valid_for_recognition(landmarks_5: np.ndarray) -> Tuple[bool, float, str]:
    """
    Check if face angle is acceptable for recognition.
    
    Rejects extreme angles (>45°) where recognition is unreliable.
    
    Args:
        landmarks_5: 5-point landmarks
        
    Returns:
        Tuple of (is_valid, angle, message)
    """
    pose = estimate_face_pose(landmarks_5)
    abs_yaw = pose["abs_yaw"]
    
    if abs_yaw > ANGLE_THRESHOLDS["extreme"]:
        return False, abs_yaw, "Face angle too extreme for recognition"
    
    if abs_yaw > ANGLE_THRESHOLDS["recognition"]:
        return False, abs_yaw, "Face turned too far, please face camera"
    
    return True, abs_yaw, "OK"


def get_angle_quality_label(abs_yaw: float) -> str:
    """Get human-readable quality label for face angle."""
    if abs_yaw <= ANGLE_THRESHOLDS["frontal"]:
        return "excellent"
    elif abs_yaw <= ANGLE_THRESHOLDS["acceptable"]:
        return "good"
    elif abs_yaw <= ANGLE_THRESHOLDS["recognition"]:
        return "fair"
    else:
        return "poor"
