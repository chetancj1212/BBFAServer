"""
Image utility functions for the face detection API
"""

import base64
import cv2
import numpy as np


def decode_base64_image(base64_string: str) -> np.ndarray:
    """
    Decode base64 string to OpenCV image

    Args:
        base64_string: Base64 encoded image string

    Returns:
        OpenCV image as numpy array (BGR format)
    """
    try:
        # Remove data URL prefix if present
        if base64_string.startswith("data:image"):
            base64_string = base64_string.split(",")[1]

        # Decode base64
        image_data = base64.b64decode(base64_string)

        # Convert to numpy array
        nparr = np.frombuffer(image_data, np.uint8)

        # Decode image
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            raise ValueError("Failed to decode image")

        return image

    except Exception as e:
        raise ValueError(f"Failed to decode base64 image: {e}")
