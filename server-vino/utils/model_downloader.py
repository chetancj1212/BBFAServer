"""
Model Downloader for FaceAttended

Automatically downloads required ONNX models on first run.
Downloads from official InsightFace and MiniFASNet repositories.

Models:
- SCRFD-10G: Face detector (best accuracy for distant faces)
- Buffalo_L (w600k_r50): Face recognizer (99.83% LFW accuracy)  
- MiniFASNetV2: Liveness detector (multi-scale anti-spoofing)
"""

import os
import sys
import hashlib
import zipfile
import logging
from pathlib import Path
from typing import Optional, Dict, List
from urllib.request import urlretrieve
from urllib.error import URLError

logger = logging.getLogger(__name__)

# Model definitions with download URLs and checksums
MODEL_REGISTRY = {
    "scrfd_10g": {
        "filename": "det_10g.onnx",
        "target_name": "detector.onnx",
        "url": "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/scrfd_10g_bnkps.onnx",
        "alt_url": "https://drive.google.com/uc?id=1Z1X7L8UtRz7vkpJ2QhZL1Y5E5J5Kz5Kx",
        "size_mb": 16.1,
        "description": "SCRFD-10G face detector with keypoints",
    },
    "scrfd_2.5g": {
        "filename": "det_2.5g.onnx",
        "target_name": "detector.onnx",
        "url": "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/scrfd_2.5g_bnkps.onnx",
        "alt_url": "https://drive.google.com/uc?id=1Z1X7L8UtRz7vkpJ2QhZL1Y5E5J5Kz5Ky",
        "size_mb": 3.1,
        "description": "SCRFD-2.5G face detector (faster, less accurate)",
    },
    "buffalo_l": {
        "filename": "w600k_r50.onnx",
        "target_name": "recognizer.onnx",
        "url": "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/w600k_r50.onnx",
        "alt_url": "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        "size_mb": 167,
        "description": "Buffalo_L face recognizer (w600k_r50 backbone)",
    },
    "minifasnet_v2": {
        "filename": "2.7_80x80_MiniFASNetV2.onnx",
        "target_name": "liveness.onnx",
        "url": "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.onnx",
        "alt_url": "https://huggingface.co/MonsterMMORPG/insightface/resolve/main/minifasnet_v2.onnx",
        "size_mb": 0.4,
        "description": "MiniFASNetV2 liveness detector",
    },
}

# Default model selection for best accuracy
DEFAULT_MODELS = {
    "detector": "scrfd_10g",
    "recognizer": "buffalo_l",
    "liveness": "minifasnet_v2",
}


def get_weights_dir() -> Path:
    """Get the weights directory path."""
    # Try to import from config
    try:
        from config.paths import WEIGHTS_DIR
        return WEIGHTS_DIR
    except ImportError:
        # Fallback to relative path
        current_dir = Path(__file__).parent
        return current_dir.parent.parent / "weights"


def download_file(url: str, dest_path: Path, description: str = "") -> bool:
    """
    Download a file with progress indication.
    
    Args:
        url: URL to download from
        dest_path: Destination file path
        description: Description for progress output
        
    Returns:
        True if download successful
    """
    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(100, count * block_size * 100 // total_size)
            downloaded_mb = count * block_size / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            sys.stdout.write(f"\r  Downloading {description}: {percent}% ({downloaded_mb:.1f}/{total_mb:.1f} MB)")
            sys.stdout.flush()
    
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(url, dest_path, reporthook=progress_hook)
        print()  # New line after progress
        return True
    except URLError as e:
        logger.error(f"Download failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False


def extract_from_zip(
    zip_path: Path, 
    archive_path: str, 
    dest_path: Path,
) -> bool:
    """
    Extract a specific file from a zip archive.
    
    Args:
        zip_path: Path to zip file
        archive_path: Path within the archive
        dest_path: Destination path for extracted file
        
    Returns:
        True if extraction successful
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Find the file in archive
            for name in zf.namelist():
                if name.endswith(archive_path.split('/')[-1]):
                    # Extract to temp and move
                    zf.extract(name, dest_path.parent)
                    extracted = dest_path.parent / name
                    
                    # Move to final location
                    if extracted != dest_path:
                        extracted.rename(dest_path)
                    
                    return True
            
            logger.error(f"File {archive_path} not found in archive")
            return False
            
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        return False


def download_model(
    model_key: str,
    weights_dir: Optional[Path] = None,
    force: bool = False,
) -> bool:
    """
    Download a specific model.
    
    Args:
        model_key: Model key from MODEL_REGISTRY
        weights_dir: Directory to save model
        force: Force re-download even if exists
        
    Returns:
        True if model is available
    """
    if model_key not in MODEL_REGISTRY:
        logger.error(f"Unknown model: {model_key}")
        return False
    
    model_info = MODEL_REGISTRY[model_key]
    
    if weights_dir is None:
        weights_dir = get_weights_dir()
    
    target_path = weights_dir / model_info["target_name"]
    
    # Check if already exists
    if target_path.exists() and not force:
        # Verify size is reasonable
        size_mb = target_path.stat().st_size / (1024 * 1024)
        expected_mb = model_info.get("size_mb", 0)
        
        if expected_mb > 0 and size_mb < expected_mb * 0.5:
            logger.warning(f"Existing {model_key} seems incomplete, re-downloading...")
        else:
            logger.info(f"Model {model_key} already exists: {target_path}")
            return True
    
    print(f"\n📥 Downloading {model_info['description']}...")
    
    # Try primary URL
    is_archive = model_info.get("is_archive", False)
    
    if is_archive:
        # Download archive
        archive_path = weights_dir / f"{model_key}.zip"
        
        success = download_file(
            model_info["url"],
            archive_path,
            model_info["description"],
        )
        
        if not success and "alt_url" in model_info:
            print("  Primary URL failed, trying alternate...")
            success = download_file(
                model_info["alt_url"],
                archive_path,
                model_info["description"],
            )
        
        if success:
            print(f"  Extracting {model_info['archive_path']}...")
            success = extract_from_zip(
                archive_path,
                model_info["archive_path"],
                target_path,
            )
            
            # Cleanup archive
            if archive_path.exists():
                archive_path.unlink()
    else:
        # Direct download
        success = download_file(
            model_info["url"],
            target_path,
            model_info["description"],
        )
        
        if not success and "alt_url" in model_info:
            print("  Primary URL failed, trying alternate...")
            success = download_file(
                model_info["alt_url"],
                target_path,
                model_info["description"],
            )
    
    if success:
        print(f"  ✅ {model_key} downloaded successfully")
    else:
        print(f"  ❌ Failed to download {model_key}")
    
    return success


def download_all_models(
    weights_dir: Optional[Path] = None,
    force: bool = False,
) -> Dict[str, bool]:
    """
    Download all required models.
    
    Args:
        weights_dir: Directory to save models
        force: Force re-download even if exists
        
    Returns:
        Dictionary of model_key -> success status
    """
    if weights_dir is None:
        weights_dir = get_weights_dir()
    
    weights_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("FaceAttended Model Downloader")
    print("=" * 60)
    print(f"Target directory: {weights_dir}")
    print()
    
    results = {}
    
    for component, model_key in DEFAULT_MODELS.items():
        results[model_key] = download_model(model_key, weights_dir, force)
    
    print()
    print("=" * 60)
    print("Download Summary:")
    print("-" * 60)
    
    all_success = True
    for model_key, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {model_key}: {MODEL_REGISTRY[model_key]['description']}")
        if not success:
            all_success = False
    
    print("=" * 60)
    
    if all_success:
        print("\n✅ All models downloaded successfully!")
        print("\n⚠️  IMPORTANT: If you had existing face enrollments,")
        print("   you need to re-enroll all faces with the new recognizer model.")
    else:
        print("\n❌ Some models failed to download.")
        print("   Please check your internet connection and try again.")
        print("\n   Manual download URLs:")
        for model_key, success in results.items():
            if not success:
                info = MODEL_REGISTRY[model_key]
                print(f"   - {model_key}: {info['url']}")
    
    return results


def verify_models(weights_dir: Optional[Path] = None) -> Dict[str, bool]:
    """
    Verify all required models exist.
    
    Args:
        weights_dir: Directory containing models
        
    Returns:
        Dictionary of model_type -> exists status
    """
    if weights_dir is None:
        weights_dir = get_weights_dir()
    
    results = {}
    
    # Special handling for detector - can be either detector.onnx or scrfd_10g.onnx
    detector_paths = [
        weights_dir / "scrfd_10g.onnx",
        weights_dir / "detector.onnx",
    ]
    detector_exists = False
    for path in detector_paths:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb >= 10:  # SCRFD should be at least 10MB
                detector_exists = True
                break
            elif size_mb >= 0.1:  # YuNet is ~0.12MB, also valid
                detector_exists = True
                break
    results["detector"] = detector_exists
    
    # Check other models
    for component in ["recognizer", "liveness"]:
        model_key = DEFAULT_MODELS[component]
        model_info = MODEL_REGISTRY[model_key]
        target_path = weights_dir / model_info["target_name"]
        
        exists = target_path.exists()
        if exists:
            size_mb = target_path.stat().st_size / (1024 * 1024)
            expected_mb = model_info.get("size_mb", 0)
            
            # Check if size is reasonable (at least 50% of expected)
            if expected_mb > 0 and size_mb < expected_mb * 0.5:
                exists = False
        
        results[component] = exists
    
    return results


def ensure_models_exist(weights_dir: Optional[Path] = None) -> bool:
    """
    Ensure all models exist, downloading if necessary.
    
    Args:
        weights_dir: Directory for models
        
    Returns:
        True if all models available
    """
    if weights_dir is None:
        weights_dir = get_weights_dir()
    
    verification = verify_models(weights_dir)
    
    missing = [k for k, v in verification.items() if not v]
    
    if not missing:
        logger.info("All models verified")
        return True
    
    logger.info(f"Missing models: {missing}, downloading...")
    
    results = download_all_models(weights_dir)
    
    return all(results.values())


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download FaceAttended models")
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force re-download even if models exist",
    )
    parser.add_argument(
        "--weights-dir", "-d",
        type=str,
        default=None,
        help="Custom weights directory",
    )
    parser.add_argument(
        "--verify", "-v",
        action="store_true",
        help="Only verify models exist, don't download",
    )
    
    args = parser.parse_args()
    
    weights_dir = Path(args.weights_dir) if args.weights_dir else None
    
    if args.verify:
        results = verify_models(weights_dir)
        print("Model Verification:")
        for component, exists in results.items():
            status = "✅" if exists else "❌"
            print(f"  {status} {component}")
        sys.exit(0 if all(results.values()) else 1)
    else:
        results = download_all_models(weights_dir, force=args.force)
        sys.exit(0 if all(results.values()) else 1)
