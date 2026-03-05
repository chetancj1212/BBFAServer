import numpy as np
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def normalize_embeddings_batch(embeddings: np.ndarray) -> List[np.ndarray]:
    """
    Normalize a batch of embeddings using vectorized operations.

    Args:
        embeddings: Batch of embeddings [N, embedding_dim]

    Returns:
        List of normalized embeddings
    """
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms > 0, norms, 1.0)
    normalized = embeddings / norms
    return [normalized[i].astype(np.float32) for i in range(len(embeddings))]


def compute_similarity(
    query_embedding: np.ndarray, database_embedding: np.ndarray
) -> float:
    """
    Compute cosine similarity between two normalized embeddings.

    Args:
        query_embedding: Query embedding (normalized)
        database_embedding: Database embedding (normalized)

    Returns:
        Similarity score in range [0, 1]
    """
    return float(np.dot(query_embedding, database_embedding))


def find_best_matches_batch(
    query_embeddings: np.ndarray,
    database_matrix: np.ndarray,
    person_ids: List[str],
    similarity_threshold: float,
    allowed_person_ids: Optional[List[str]] = None,
) -> List[Tuple[Optional[str], float]]:
    """
    Find best matching persons for multiple query embeddings using vectorized operations.
    
    This is significantly faster than calling find_best_match in a loop:
    - For 60 faces × 100 persons: ~6000 sequential ops → 1 matrix multiplication
    
    Args:
        query_embeddings: Query embeddings as numpy array [N_queries, embedding_dim]
        database_matrix: Database embeddings as stacked numpy array [N_persons, embedding_dim]
        person_ids: List of person IDs corresponding to database_matrix rows
        similarity_threshold: Minimum similarity threshold for recognition
        allowed_person_ids: Optional list of allowed person IDs for filtering
        
    Returns:
        List of tuples (best_person_id, best_similarity) for each query
    """
    if len(query_embeddings) == 0:
        return []
    
    if database_matrix is None or len(database_matrix) == 0 or len(person_ids) == 0:
        return [(None, 0.0) for _ in range(len(query_embeddings))]
    
    # Filter by allowed person IDs if provided
    if allowed_person_ids is not None:
        allowed_set = set(allowed_person_ids)
        mask = [pid in allowed_set for pid in person_ids]
        if not any(mask):
            return [(None, 0.0) for _ in range(len(query_embeddings))]
        
        mask_indices = [i for i, m in enumerate(mask) if m]
        database_matrix = database_matrix[mask_indices]
        person_ids = [person_ids[i] for i in mask_indices]
    
    # Ensure query_embeddings is 2D
    if query_embeddings.ndim == 1:
        query_embeddings = query_embeddings.reshape(1, -1)
    
    # Vectorized cosine similarity: [N_queries, embedding_dim] @ [embedding_dim, N_persons]
    # Result shape: [N_queries, N_persons]
    similarities = query_embeddings @ database_matrix.T
    
    # Find best match for each query
    best_indices = np.argmax(similarities, axis=1)
    best_scores = similarities[np.arange(len(query_embeddings)), best_indices]
    
    # Build results
    results = []
    for idx, (best_idx, score) in enumerate(zip(best_indices, best_scores)):
        if score >= similarity_threshold:
            results.append((person_ids[best_idx], float(score)))
        else:
            results.append((None, float(score)))
    
    logger.debug(f"[BATCH_MATCH] Matched {len(query_embeddings)} faces against {len(person_ids)} persons")
    
    return results


def find_best_match(
    query_embedding: np.ndarray,
    database: Dict[str, np.ndarray],
    similarity_threshold: float,
    allowed_person_ids: Optional[List[str]] = None,
) -> Tuple[Optional[str], float]:
    """
    Find best matching person in database (single query version).

    Args:
        query_embedding: Query embedding (normalized)
        database: Dictionary mapping person_id to embedding
        similarity_threshold: Minimum similarity threshold for recognition
        allowed_person_ids: Optional list of allowed person IDs for filtering

    Returns:
        Tuple of (best_person_id, best_similarity)
        - best_person_id: Person ID if match found above threshold, else None
        - best_similarity: Best similarity score found
    """
    if not database:
        logger.debug("Empty database, no match possible")
        return None, 0.0

    # Filter by allowed person IDs if provided
    if allowed_person_ids is not None:
        database = {
            pid: emb for pid, emb in database.items() if pid in allowed_person_ids
        }
        if not database:
            return None, 0.0

    best_person_id = None
    best_similarity = 0.0

    for person_id, stored_embedding in database.items():
        similarity = compute_similarity(query_embedding, stored_embedding)
        # Removed hot-path logging - use debug level only
        logger.debug(f"[MATCH] {person_id}: {similarity:.4f}")

        if similarity > best_similarity:
            best_similarity = similarity
            best_person_id = person_id

    logger.debug(f"[BEST] person_id={best_person_id}, similarity={best_similarity:.4f}, threshold={similarity_threshold}")
    
    # Only return person_id if similarity meets threshold
    if best_similarity >= similarity_threshold:
        return best_person_id, best_similarity
    else:
        return None, best_similarity

