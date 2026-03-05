import logging
import os
import uvicorn

from fastapi import FastAPI

from core.lifespan import lifespan
from api.endpoints import router
from middleware.cors import setup_cors
from middleware.rate_limit import setup_rate_limiting

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Attended",
    description="A desktop application for automated attendance tracking using Artificial Intelligence.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
setup_cors(app)

# Configure rate limiting (Scalability Fix #3)
setup_rate_limiting(app)

# Include API router
app.include_router(router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Face Detection API is running", "status": "healthy"}


@app.get("/models")
async def get_available_models():
    """Get information about available models"""
    face_detector = getattr(app.state, "face_detector", None)
    liveness_detector = getattr(app.state, "liveness_detector", None)
    face_recognizer = getattr(app.state, "face_recognizer", None)

    models_info = {}

    # Check if face_detector exists and is actually functional
    if (
        face_detector
        and hasattr(face_detector, "session")
        and face_detector.session is not None
    ):
        models_info["face_detector"] = {"available": True}
    else:
        models_info["face_detector"] = {"available": False}

    # Check if liveness_detector exists and is actually functional
    if (
        liveness_detector
        and hasattr(liveness_detector, "ort_session")
        and liveness_detector.ort_session is not None
    ):
        models_info["liveness_detector"] = {"available": True}
    else:
        models_info["liveness_detector"] = {"available": False}

    # Check if face_recognizer exists and is actually functional
    if (
        face_recognizer
        and hasattr(face_recognizer, "session")
        and face_recognizer.session is not None
    ):
        models_info["face_recognizer"] = {"available": True}
    else:
        models_info["face_recognizer"] = {"available": False}

    return {"models": models_info}


if __name__ == "__main__":
    workers = int(os.environ.get("WORKERS", "1"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(
        "main:app" if workers > 1 else app,
        host=host,
        port=8700,
        workers=workers if workers > 1 else None,
    )
