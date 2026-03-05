"""
Utility functions package

Contains image processing utilities, WebSocket management, and face serialization.
"""

from .image_utils import decode_base64_image
from .face_utils import serialize_faces

__all__ = [
    "decode_base64_image",
    "serialize_faces",
]

