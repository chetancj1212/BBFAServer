"""
ArcFace/Buffalo Face Recognizer - InsightFace Recognition Model

High-accuracy face recognition using the Buffalo model from InsightFace.
Buffalo_L uses w600k_r50 backbone - 99.83% accuracy on LFW.

Model: Buffalo_L (w600k_r50.onnx)
Input: 112x112 RGB normalized face
Output: 512-dimensional embedding
"""

import cv2
import numpy as np
import onnxruntime as ort
from typing import List, Dict, Tuple, Optional, Any
import logging

from database.face import FaceDatabaseManager
from .preprocess import (
    align_face, 
    enhance_face_image,
    upscale_small_face,
    scale_landmarks,
)

logger = logging.getLogger(__name__)


class ArcFaceRecognizer:
    """
    ArcFace-based Face Recognizer using Buffalo_L model.
    
    Supports batch processing for multiple faces.
    Optimized for CPU inference.
    """
    
    def __init__(
        self,
        model_path: str,
        input_size: Tuple[int, int] = (112, 112),
        similarity_threshold: float = 0.4,
        providers: Optional[List] = None,
        database_path: Optional[str] = None,
        session_options: Optional[Dict[str, Any]] = None,
        embedding_dimension: int = 512,
    ):
        """
        Initialize ArcFace recognizer.
        
        Args:
            model_path: Path to ONNX model file
            input_size: Input size (width, height) - 112x112 standard
            similarity_threshold: Cosine similarity threshold for matching
            providers: ONNX Runtime execution providers
            database_path: Path to face database
            session_options: Additional session options
            embedding_dimension: Embedding vector dimension (512 standard)
        """
        self.model_path = model_path
        self.input_size = input_size
        self.similarity_threshold = similarity_threshold
        self.embedding_dim = embedding_dimension
        
        # Preprocessing constants for ArcFace/Buffalo
        self.INPUT_MEAN = 127.5
        self.INPUT_STD = 127.5
        
        # Initialize session (prefer OpenVINO, fallback to onnxruntime)
        try:
            try:
                from config.openvino_backend import create_session
            except ImportError:
                from server.config.openvino_backend import create_session
            self.session = create_session(model_path)
        except (ImportError, Exception) as e:
            logger.warning(f"OpenVINO backend unavailable: {e}, using onnxruntime")
            if providers is None:
                providers = [("CPUExecutionProvider", {"arena_extend_strategy": "kSameAsRequested"})]
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.intra_op_num_threads = 0
            sess_options.inter_op_num_threads = 0
            if session_options:
                for key, value in session_options.items():
                    if hasattr(sess_options, key):
                        setattr(sess_options, key, value)
            self.session = ort.InferenceSession(
                model_path, sess_options=sess_options, providers=providers,
            )
        
        try:
            self.input_name = self.session.get_inputs()[0].name
            
            # Get output dimension from model
            output_shape = self.session.get_outputs()[0].shape
            if output_shape and len(output_shape) > 1:
                self.embedding_dim = output_shape[-1]
            
            active_providers = self.session.get_providers()
            logger.info(f"ArcFace initialized: {input_size}, embedding_dim={self.embedding_dim}")
            logger.info(f"ArcFace active providers: {active_providers}")
            
        except Exception as e:
            logger.error(f"Failed to load ArcFace model: {e}")
            raise
        
        # Database Layer
        if database_path:
            if database_path.endswith(".json"):
                database_path = database_path.replace(".json", ".db")
            self.db_manager = FaceDatabaseManager(database_path)
        else:
            self.db_manager = None
            logger.warning("No database path provided, running without persistence")
        
        # Cache Layer
        self._persons_cache = None
        self._cache_timestamp = 0
        self._cache_ttl = 1.0
        
        # Matrix cache for batch matching
        self._database_matrix = None
        self._database_person_ids = None
        self._matrix_cache_timestamp = 0
    
    def _align_face(
        self, image: np.ndarray, landmarks_5: np.ndarray
    ) -> np.ndarray:
        """
        Align face using 5-point landmarks.
        
        Args:
            image: Input BGR image
            landmarks_5: 5-point facial landmarks
            
        Returns:
            Aligned face image (112x112)
        """
        return align_face(image, np.array(landmarks_5), self.input_size)
    
    def _preprocess_face(self, aligned_face: np.ndarray) -> np.ndarray:
        """
        Preprocess aligned face for model inference.
        
        Args:
            aligned_face: Aligned face image (BGR)
            
        Returns:
            Preprocessed tensor [1, 3, H, W]
        """
        # Optionally enhance for poor lighting
        # enhanced = enhance_face_image(aligned_face)
        
        # Convert BGR to RGB
        rgb = cv2.cvtColor(aligned_face, cv2.COLOR_BGR2RGB)
        
        # Normalize: (x - 127.5) / 127.5
        normalized = (rgb.astype(np.float32) - self.INPUT_MEAN) / self.INPUT_STD
        
        # NCHW format with batch dimension
        tensor = normalized.transpose(2, 0, 1)[np.newaxis, ...]
        
        return tensor
    
    def _extract_embedding(
        self, image: np.ndarray, landmarks_5: List, bbox: Optional[List] = None
    ) -> Optional[np.ndarray]:
        """
        Extract face embedding for a single face.
        
        For distant/small faces, applies super-resolution before alignment
        to improve recognition accuracy.
        
        Args:
            image: Input BGR image
            landmarks_5: 5-point landmarks
            bbox: Optional bounding box for small face detection
            
        Returns:
            Normalized embedding vector or None on failure
        """
        try:
            # Validate landmarks format
            if landmarks_5 is None or len(landmarks_5) != 5:
                logger.error(f"Invalid landmarks: expected 5 points, got {len(landmarks_5) if landmarks_5 else 0}")
                return None
            
            landmarks = np.array(landmarks_5, dtype=np.float32)
            
            # Validate landmarks shape
            if landmarks.shape != (5, 2):
                logger.error(f"Invalid landmarks shape: expected (5, 2), got {landmarks.shape}")
                return None
            
            # Check if face is small (distant) and needs upscaling
            if bbox is not None:
                # bbox is [x, y, width, height] format
                x, y, w, h = bbox[:4]
                face_size = min(w, h)
                
                # Convert to x1, y1, x2, y2 for upscale_small_face
                bbox_xyxy = (x, y, x + w, y + h)
                
                # For small faces (< 80px), use super-resolution pipeline
                if face_size < 80:
                    upscaled_crop, scale = upscale_small_face(
                        image, bbox_xyxy,
                        min_size_threshold=80,
                        target_crop_size=160
                    )
                    
                    # Scale landmarks to match upscaled crop
                    scaled_landmarks = scale_landmarks(
                        landmarks, bbox_xyxy, scale
                    )
                    
                    # Align from upscaled crop
                    aligned = align_face(upscaled_crop, scaled_landmarks, self.input_size)
                    
                    # Apply enhancement for small faces
                    aligned = enhance_face_image(aligned)
                    
                    logger.debug(f"Used super-resolution for small face: {face_size}px -> {int(face_size * scale)}px")
                else:
                    aligned = self._align_face(image, landmarks)
            else:
                aligned = self._align_face(image, landmarks)
            
            input_tensor = self._preprocess_face(aligned)
            
            outputs = self.session.run(None, {self.input_name: input_tensor})
            embedding = outputs[0][0]
            
            # L2 normalize
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            return embedding.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Embedding extraction failed: {e}")
            return None
    
    def _extract_embeddings_batch(
        self, image: np.ndarray, faces_data: List[Dict]
    ) -> List[Optional[np.ndarray]]:
        """
        Extract embeddings for multiple faces in batch.
        
        Handles small/distant faces with super-resolution for improved accuracy.
        
        Args:
            image: Input BGR image
            faces_data: List of face dicts with 'landmarks_5' and optionally 'bbox'
            
        Returns:
            List of embeddings (None for failed extractions)
        """
        if not faces_data:
            return []
        
        # Separate small and normal faces for different processing
        aligned_faces = []
        valid_indices = []
        small_face_threshold = 80  # pixels
        
        for i, face in enumerate(faces_data):
            landmarks = face.get("landmarks_5")
            if landmarks is None:
                continue
            
            try:
                landmarks_arr = np.array(landmarks, dtype=np.float32)
                bbox = face.get("bbox")
                
                # Check if this is a small face that needs super-resolution
                if bbox is not None:
                    x1, y1, x2, y2 = bbox[:4]
                    face_size = min(x2 - x1, y2 - y1)
                    
                    if face_size < small_face_threshold:
                        # Use super-resolution pipeline for small faces
                        upscaled_crop, scale = upscale_small_face(
                            image, tuple(bbox[:4]),
                            min_size_threshold=small_face_threshold,
                            target_crop_size=160
                        )
                        
                        scaled_landmarks = scale_landmarks(
                            landmarks_arr, tuple(bbox[:4]), scale
                        )
                        
                        aligned = align_face(upscaled_crop, scaled_landmarks, self.input_size)
                        aligned = enhance_face_image(aligned)
                    else:
                        aligned = self._align_face(image, landmarks_arr)
                else:
                    aligned = self._align_face(image, landmarks_arr)
                
                aligned_faces.append(aligned)
                valid_indices.append(i)
            except Exception as e:
                logger.warning(f"Face alignment failed: {e}")
        
        if not aligned_faces:
            return [None] * len(faces_data)
        
        # Batch preprocess
        batch_input = np.concatenate([
            self._preprocess_face(face) for face in aligned_faces
        ], axis=0)
        
        # Batch inference
        try:
            outputs = self.session.run(None, {self.input_name: batch_input})
            embeddings_raw = outputs[0]
        except Exception as e:
            logger.error(f"Batch inference failed: {e}")
            return [None] * len(faces_data)
        
        # L2 normalize all embeddings
        norms = np.linalg.norm(embeddings_raw, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)
        embeddings_normalized = embeddings_raw / norms
        
        # Map back to original indices
        results = [None] * len(faces_data)
        for batch_idx, orig_idx in enumerate(valid_indices):
            results[orig_idx] = embeddings_normalized[batch_idx].astype(np.float32)
        
        return results
    
    def _get_database(self) -> Dict[str, np.ndarray]:
        """Get person database with caching."""
        import time
        current_time = time.time()
        
        if (
            self._persons_cache is None
            or (current_time - self._cache_timestamp) > self._cache_ttl
        ):
            if self.db_manager:
                self._persons_cache = self.db_manager.get_all_persons()
            else:
                self._persons_cache = {}
            self._cache_timestamp = current_time
        
        return self._persons_cache
    
    def _get_database_matrix(self) -> Tuple[Optional[np.ndarray], List[str]]:
        """Get database as matrix for vectorized batch matching."""
        import time
        current_time = time.time()
        
        if (
            self._database_matrix is None
            or (current_time - self._matrix_cache_timestamp) > self._cache_ttl
        ):
            database = self._get_database()
            
            if not database:
                self._database_matrix = None
                self._database_person_ids = []
            else:
                self._database_person_ids = list(database.keys())
                self._database_matrix = np.stack(
                    [database[pid] for pid in self._database_person_ids]
                )
            
            self._matrix_cache_timestamp = current_time
        
        return self._database_matrix, self._database_person_ids
    
    def _find_best_match(
        self, 
        embedding: np.ndarray,
        allowed_person_ids: Optional[List[str]] = None,
    ) -> Tuple[Optional[str], float]:
        """Find best matching person for an embedding."""
        database = self._get_database()
        
        if not database:
            return None, 0.0
        
        best_person_id = None
        best_similarity = 0.0
        
        for person_id, stored_embedding in database.items():
            if allowed_person_ids and person_id not in allowed_person_ids:
                continue
            
            # Cosine similarity (embeddings are normalized)
            similarity = float(np.dot(embedding, stored_embedding))
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_person_id = person_id
        
        if best_similarity < self.similarity_threshold:
            return None, best_similarity
        
        return best_person_id, best_similarity
    
    def _refresh_cache(self):
        """Refresh cache after database modifications."""
        import time
        
        if self.db_manager:
            self._persons_cache = self.db_manager.get_all_persons()
            self._cache_timestamp = time.time()
            
            if self._persons_cache:
                self._database_person_ids = list(self._persons_cache.keys())
                self._database_matrix = np.stack(
                    [self._persons_cache[pid] for pid in self._database_person_ids]
                )
            else:
                self._database_matrix = None
                self._database_person_ids = []
            self._matrix_cache_timestamp = time.time()
        else:
            self._persons_cache = None
            self._cache_timestamp = 0
            self._database_matrix = None
            self._database_person_ids = []
            self._matrix_cache_timestamp = 0
    
    def recognize_face(
        self,
        image: np.ndarray,
        landmarks_5: List,
        allowed_person_ids: Optional[List[str]] = None,
        bbox: Optional[List] = None,
    ) -> Dict:
        """
        Recognize a single face.
        
        For distant/small faces, automatically applies super-resolution
        to improve recognition accuracy.
        
        Args:
            image: Input BGR image
            landmarks_5: 5-point facial landmarks
            allowed_person_ids: Optional list to restrict matching
            bbox: Optional bounding box for small face enhancement
            
        Returns:
            Recognition result dictionary
        """
        try:
            embedding = self._extract_embedding(image, landmarks_5, bbox)
            
            if embedding is None:
                return {
                    "person_id": None,
                    "similarity": 0.0,
                    "success": False,
                    "error": "Failed to extract embedding",
                }
            
            person_id, similarity = self._find_best_match(embedding, allowed_person_ids)
            
            return {
                "person_id": person_id,
                "similarity": similarity,
                "success": person_id is not None,
            }
            
        except Exception as e:
            logger.error(f"Face recognition error: {e}")
            return {
                "person_id": None,
                "similarity": 0.0,
                "success": False,
                "error": str(e),
            }
    
    def recognize_faces_batch(
        self,
        image: np.ndarray,
        faces_data: List[Dict],
        allowed_person_ids: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Recognize multiple faces using batch processing.
        
        Args:
            image: Input BGR image
            faces_data: List of face dicts with landmarks_5
            allowed_person_ids: Optional list to restrict matching
            
        Returns:
            List of recognition results
        """
        if not faces_data:
            return []
        
        # Extract all embeddings in batch
        embeddings = self._extract_embeddings_batch(image, faces_data)
        
        # Get database matrix for vectorized matching
        db_matrix, person_ids = self._get_database_matrix()
        
        results = []
        
        for i, face in enumerate(faces_data):
            embedding = embeddings[i]
            
            if embedding is None:
                results.append({
                    "track_id": face.get("track_id"),
                    "person_id": None,
                    "similarity": 0.0,
                    "success": False,
                    "error": "Failed to extract embedding",
                })
                continue
            
            if db_matrix is None or len(person_ids) == 0:
                results.append({
                    "track_id": face.get("track_id"),
                    "person_id": None,
                    "similarity": 0.0,
                    "success": False,
                })
                continue
            
            # Vectorized similarity computation
            similarities = np.dot(db_matrix, embedding)
            
            # Filter by allowed_person_ids if specified
            if allowed_person_ids:
                mask = np.array([pid in allowed_person_ids for pid in person_ids])
                similarities = np.where(mask, similarities, -1.0)
            
            best_idx = np.argmax(similarities)
            best_similarity = float(similarities[best_idx])
            
            if best_similarity >= self.similarity_threshold:
                person_id = person_ids[best_idx]
            else:
                person_id = None
            
            results.append({
                "track_id": face.get("track_id"),
                "person_id": person_id,
                "similarity": best_similarity,
                "success": person_id is not None,
            })
        
        return results
    
    def add_person(self, person_id: str, embedding: np.ndarray) -> bool:
        """Add a person to the database."""
        if not self.db_manager:
            return False
        
        result = self.db_manager.add_person(person_id, embedding)
        if result:
            self._refresh_cache()
        return result
    
    def register_face(
        self,
        person_id: str,
        image: np.ndarray,
        landmarks_5: List,
    ) -> Dict:
        """
        Register a new face for a person.
        
        Args:
            person_id: Person identifier
            image: Input BGR image
            landmarks_5: 5-point landmarks
            
        Returns:
            Registration result
        """
        try:
            embedding = self._extract_embedding(image, landmarks_5)
            
            if embedding is None:
                return {
                    "success": False,
                    "error": "Failed to extract embedding",
                }
            
            result = self.add_person(person_id, embedding)
            
            return {
                "success": result,
                "person_id": person_id if result else None,
            }
            
        except Exception as e:
            logger.error(f"Face registration error: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def remove_person(self, person_id: str) -> bool:
        """Remove a person from the database."""
        if not self.db_manager:
            return False
        
        result = self.db_manager.remove_person(person_id)
        if result:
            self._refresh_cache()
        return result
    
    def get_all_person_ids(self) -> List[str]:
        """Get all registered person IDs."""
        database = self._get_database()
        return list(database.keys())
    
    # ==========================================================================
    # Additional methods for compatibility with existing codebase
    # ==========================================================================
    
    def register_person(
        self, person_id: str, image: np.ndarray, landmarks_5: List
    ) -> Dict:
        """
        Register a new person with face embedding.
        
        Args:
            person_id: Person identifier
            image: Input BGR image
            landmarks_5: 5-point facial landmarks
            
        Returns:
            Registration result dictionary
        """
        try:
            embedding = self._extract_embedding(image, landmarks_5)
            
            if embedding is None:
                return {
                    "success": False,
                    "error": "Failed to extract embedding",
                    "person_id": person_id,
                }
            
            if self.db_manager:
                save_success = self.db_manager.add_person(person_id, embedding)
                stats = self.db_manager.get_stats()
                total_persons = stats.get("total_persons", 0)
                self._refresh_cache()
            else:
                save_success = False
                total_persons = 0
                logger.warning("No database manager available for registration")
            
            return {
                "success": True,
                "person_id": person_id,
                "database_saved": save_success,
                "total_persons": total_persons,
            }
            
        except Exception as e:
            logger.error(f"Person registration failed: {e}")
            return {"success": False, "error": str(e), "person_id": person_id}
    
    def get_all_persons(self) -> List[str]:
        """Get list of all registered person IDs."""
        if self.db_manager:
            all_persons = self.db_manager.get_all_persons()
            return list(all_persons.keys())
        return []
    
    def update_person_id(self, old_person_id: str, new_person_id: str) -> Dict:
        """Update a person's ID in the database."""
        try:
            if self.db_manager:
                updated_count = self.db_manager.update_person_id(
                    old_person_id, new_person_id
                )
                if updated_count > 0:
                    self._refresh_cache()
                    return {
                        "success": True,
                        "message": f"Person '{old_person_id}' renamed to '{new_person_id}' successfully",
                        "updated_records": updated_count,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Person '{old_person_id}' not found or '{new_person_id}' already exists",
                        "updated_records": 0,
                    }
            else:
                return {
                    "success": False,
                    "error": "No database manager available",
                    "updated_records": 0,
                }
        except Exception as e:
            logger.error(f"Person update failed: {e}")
            return {"success": False, "error": str(e), "updated_records": 0}
    
    def get_stats(self) -> Dict:
        """Get face recognition statistics."""
        total_persons = 0
        persons = []
        
        if self.db_manager:
            stats = self.db_manager.get_stats()
            total_persons = stats.get("total_persons", 0)
            persons = self.db_manager.get_all_persons_with_details()
        
        return {"total_persons": total_persons, "persons": persons}
    
    def set_similarity_threshold(self, threshold: float):
        """Update similarity threshold for recognition."""
        self.similarity_threshold = threshold
    
    def clear_database(self) -> Dict:
        """Clear all persons from the database."""
        try:
            if self.db_manager:
                clear_success = self.db_manager.clear_database()
                
                if clear_success:
                    self._refresh_cache()
                    return {"success": True, "database_saved": True, "total_persons": 0}
                else:
                    return {"success": False, "error": "Failed to clear database"}
            else:
                return {"success": False, "error": "No database manager available"}
        except Exception as e:
            logger.error(f"Database clearing failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _invalidate_cache(self):
        """Invalidate cache without refreshing."""
        self._persons_cache = None
        self._cache_timestamp = 0
    
    def register_person_embedding(
        self, person_id: str, embedding: np.ndarray, angle: str = "front"
    ) -> Dict:
        """
        Register a person embedding directly with angle metadata.
        Used for multi-angle registration.
        
        Args:
            person_id: Person identifier
            embedding: Pre-extracted embedding
            angle: Face angle ('front', 'left', 'right')
            
        Returns:
            Registration result dictionary
        """
        try:
            if not self.db_manager:
                return {
                    "success": False,
                    "error": "No database manager available",
                }
            
            # Use angle-aware storage
            save_success = self.db_manager.add_person_with_angle(person_id, embedding, angle)
            
            if save_success:
                self._refresh_cache()
                stats = self.db_manager.get_stats()
                return {
                    "success": True,
                    "person_id": person_id,
                    "angle": angle,
                    "total_persons": stats.get("total_persons", 0),
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to save embedding",
                }
            
        except Exception as e:
            logger.error(f"Embedding registration failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_person_count(self) -> int:
        """Get total number of registered persons."""
        if self.db_manager:
            stats = self.db_manager.get_stats()
            return stats.get("total_persons", 0)
        return 0
