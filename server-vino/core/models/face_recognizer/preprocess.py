import cv2
import numpy as np
from typing import List, Tuple


# Reference points for face alignment (112x112 standard)
REFERENCE_POINTS = np.array(
    [
        [38.2946, 51.6963],  # left eye
        [73.5318, 51.5014],  # right eye
        [56.0252, 71.7366],  # nose
        [41.5493, 92.3655],  # left mouth
        [70.7299, 92.2041],  # right mouth
    ],
    dtype=np.float32,
)


def align_face(
    image: np.ndarray, landmarks: np.ndarray, input_size: Tuple[int, int]
) -> np.ndarray:
    """
    Align face using similarity transformation based on 5 landmarks.

    Args:
        image: Input image (BGR format)
        landmarks: 5 facial landmarks as numpy array
        input_size: Target size (width, height) for aligned face

    Returns:
        Aligned face image
    """
    tform, _ = cv2.estimateAffinePartial2D(
        landmarks,
        REFERENCE_POINTS,
        method=cv2.LMEDS,
        maxIters=1,
        refineIters=0,
    )

    if tform is None:
        raise ValueError("Failed to compute similarity transformation matrix")

    aligned_face = cv2.warpAffine(
        image,
        tform,
        input_size,
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )

    return aligned_face


def enhance_face_image(image: np.ndarray) -> np.ndarray:
    """
    Apply CLAHE (Contrast Limited Adaptive Histogram Equalization) to enhance
    face image quality, especially useful for poor lighting conditions.
    
    Args:
        image: Input face image (BGR format)
        
    Returns:
        Enhanced face image (BGR format)
    """
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    
    # Apply CLAHE to the L channel (luminance)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    l_enhanced = clahe.apply(l)
    
    # Merge back and convert to BGR
    lab_enhanced = cv2.merge([l_enhanced, a, b])
    enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
    
    return enhanced


def upscale_small_face(
    image: np.ndarray,
    bbox: Tuple[int, int, int, int],
    min_size_threshold: int = 80,
    target_crop_size: int = 160,
) -> Tuple[np.ndarray, float]:
    """
    Upscale small faces before alignment for better recognition at distance.
    
    When faces are far away (small bounding box), upscaling before alignment
    significantly improves landmark detection and recognition accuracy.
    
    Args:
        image: Input image (BGR format)
        bbox: Face bounding box (x1, y1, x2, y2)
        min_size_threshold: Faces smaller than this get upscaled
        target_crop_size: Target size after upscaling
        
    Returns:
        Tuple of (processed_crop, scale_factor)
    """
    x1, y1, x2, y2 = map(int, bbox)
    face_width = x2 - x1
    face_height = y2 - y1
    face_size = min(face_width, face_height)
    
    # Add padding around face for better context (20% each side)
    pad_x = int(face_width * 0.2)
    pad_y = int(face_height * 0.2)
    
    # Clamp to image boundaries
    h, w = image.shape[:2]
    x1_pad = max(0, x1 - pad_x)
    y1_pad = max(0, y1 - pad_y)
    x2_pad = min(w, x2 + pad_x)
    y2_pad = min(h, y2 + pad_y)
    
    # Extract face region with padding
    face_crop = image[y1_pad:y2_pad, x1_pad:x2_pad]
    
    if face_size < min_size_threshold:
        # Calculate scale factor to reach target size
        scale = target_crop_size / face_size
        scale = min(scale, 4.0)  # Cap at 4x to avoid artifacts
        
        # Use INTER_LANCZOS4 for best quality upscaling
        new_width = int(face_crop.shape[1] * scale)
        new_height = int(face_crop.shape[0] * scale)
        upscaled = cv2.resize(
            face_crop, 
            (new_width, new_height), 
            interpolation=cv2.INTER_LANCZOS4
        )
        
        # Apply slight sharpening to reduce blur from upscaling
        kernel = np.array([
            [0, -0.5, 0],
            [-0.5, 3, -0.5],
            [0, -0.5, 0]
        ]) / 1.0
        sharpened = cv2.filter2D(upscaled, -1, kernel)
        
        # Blend sharpened with original (50% strength)
        result = cv2.addWeighted(upscaled, 0.5, sharpened, 0.5, 0)
        
        return result, scale
    
    return face_crop, 1.0


def scale_landmarks(
    landmarks: np.ndarray,
    bbox: Tuple[int, int, int, int],
    scale_factor: float,
    padding_ratio: float = 0.2,
) -> np.ndarray:
    """
    Scale landmarks to match upscaled face crop coordinates.
    
    Args:
        landmarks: Original 5-point landmarks
        bbox: Original face bounding box
        scale_factor: How much the face was upscaled
        padding_ratio: Padding ratio used in upscale_small_face
        
    Returns:
        Scaled landmarks in crop coordinate space
    """
    x1, y1, x2, y2 = map(int, bbox)
    face_width = x2 - x1
    face_height = y2 - y1
    
    # Calculate padding offset
    pad_x = int(face_width * padding_ratio)
    pad_y = int(face_height * padding_ratio)
    
    # Convert to crop coordinates, then scale
    scaled_landmarks = landmarks.copy().astype(np.float32)
    scaled_landmarks[:, 0] = (landmarks[:, 0] - x1 + pad_x) * scale_factor
    scaled_landmarks[:, 1] = (landmarks[:, 1] - y1 + pad_y) * scale_factor
    
    return scaled_landmarks


def preprocess_image(
    aligned_face: np.ndarray, input_mean: float = 127.5, input_std: float = 127.5
) -> np.ndarray:
    """
    Preprocess aligned face for model inference.

    Args:
        aligned_face: Aligned face image (BGR format)
        input_mean: Mean value for normalization
        input_std: Standard deviation for normalization

    Returns:
        Preprocessed tensor with shape [C, H, W] (no batch dimension)
    """
    rgb_image = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)
    normalized = (rgb_image.astype(np.float32) - input_mean) / input_std
    input_tensor = np.transpose(normalized, (2, 0, 1))
    return input_tensor


def align_faces_batch(
    image: np.ndarray, face_data_list: List[dict], input_size: Tuple[int, int],
    enhance: bool = True
) -> List[np.ndarray]:
    """
    Align multiple faces from a single image.

    Args:
        image: Input image (BGR format)
        face_data_list: List of face data dicts with 'landmarks_5' key
        input_size: Target size (width, height) for aligned faces
        enhance: Whether to apply CLAHE enhancement for better recognition

    Returns:
        List of aligned face images
    """
    aligned_faces = []
    for face_data in face_data_list:
        try:
            landmarks_5 = face_data.get("landmarks_5")
            if landmarks_5 is None:
                continue
            landmarks = np.array(landmarks_5, dtype=np.float32)

            if landmarks.shape != (5, 2):
                continue

            aligned_face = align_face(image, landmarks, input_size)
            
            # Apply CLAHE enhancement for better recognition in poor conditions
            if enhance:
                aligned_face = enhance_face_image(aligned_face)
                
            aligned_faces.append(aligned_face)
        except Exception:
            continue

    return aligned_faces


def preprocess_batch(
    aligned_faces: List[np.ndarray],
    input_mean: float = 127.5,
    input_std: float = 127.5,
) -> np.ndarray:
    """
    Preprocess multiple aligned faces into a batch tensor.

    Args:
        aligned_faces: List of aligned face images
        input_mean: Mean value for normalization
        input_std: Standard deviation for normalization

    Returns:
        Batch tensor [N, C, H, W] ready for model inference
    """
    if not aligned_faces:
        return np.array([])

    batch_tensors = [
        preprocess_image(face, input_mean, input_std) for face in aligned_faces
    ]
    return np.stack(batch_tensors, axis=0)
