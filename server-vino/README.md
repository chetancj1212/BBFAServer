# Face Attended Backend Server

This is the backend server for **Face Attended (Desktop Application for Automated Attendance Tracking)**. It provides a RESTful API and WebSocket interface for face detection, recognition, liveness checking, and attendance management.

## 🏗 Architecture

The backend is built using **FastAPI** and **Python**, designed to run locally as part of a desktop application or as a standalone server.

### Key Components:

- **API Layer (`api/`)**: REST endpoints for managing groups, members, and attendance records.
- **Core Logic (`core/`)**:
  - **Face Detection**: Uses OpenCV/ONNX models to detect faces in images.
  - **Face Recognition**: Generates embeddings for faces and compares them with registered members.
  - **Liveness Detection**: Anti-spoofing checks to ensure the face is real (not a photo or screen).
- **Database (`database/`)**: SQLite database (`data/attendance.db`) for storing attendance data, groups, and logs.
- **Real-time Updates**: WebSockets for broadcasting attendance events to the frontend.

## 🚀 Technology Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (high-performance, async).
- **Server**: [Uvicorn](https://www.uvicorn.org/) (ASGI server).
- **Computer Vision**:
  - `opencv-python`: Image processing.
  - `onnxruntime`: Running ML models optimized for performance.
  - `scipy`: Mathematical operations (distance calculations).
- **Data Validation**: `pydantic`.
- **Database**: SQLite.
- **Utilities**: `ulid` (Unique ID generation), `python-multipart` (File uploads).

## 📂 Project Structure

```
server/
├── api/                # API Routes and Schemas
│   ├── routes/         # Endpoints (attendance, detection, recognition)
│   └── endpoints.py    # Router aggregation
├── core/               # Core Application Logic
│   ├── models/         # ML Model wrappers (FaceNet, etc.)
│   └── lifespan.py     # Startup/Shutdown logic (Model loading)
├── data/               # SQLite database storage
├── database/           # Database managers/abstractions
├── middleware/         # CORS and other middleware
├── weights/            # ML Model weights (.onnx files)
├── main.py             # Application Entry Point
└── requirements.txt    # Python Dependencies
```

## ✨ Features

1.  **Automated Attendance**:
    - Recognizes registered members via camera feed.
    - Automatically logs attendance with timestamps.
    - **Cooldown System**: Prevents spamming records (default 10s cooldown).
    - **Late Tracking**: Configurable "Late Thresholds" per group.

2.  **Management API**:
    - **Groups**: Create/Manage classes or employee groups.
    - **Members**: Register individuals with their face embeddings.
    - **Sessions**: Daily summaries of attendance (Present/Late/Absent).

3.  **Security**:
    - **Liveness Detection**: Prevents spoofing with photos.
    - **Data Privacy**: Local processing and storage (SQLite).

## 🛠️ Installation & Usage

### Prerequisites

- Python 3.10+
- pip

### Setup

1.  Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

2.  Run the server:

    ```bash
    python main.py
    ```

    - The server will start on `http://127.0.0.1:8700`.
    - API Documentation (Swagger UI) is available at `http://127.0.0.1:8700/docs`.

## 🔌 API Endpoints Overview

- `GET /`: Health check.
- `GET /models`: Check status of ML models.
- **Attendance**:
  - `POST /attendance/groups`: Create a group.
  - `POST /attendance/members`: Add a member.
  - `POST /attendance/events`: Trigger an attendance event (used by recognition system).
  - `GET /attendance/records`: precise logs.
  - `GET /attendance/sessions`: Daily summaries.

## 📦 Building

The backend is configured to be frozen into an executable using **PyInstaller**.

- See `build_backend.py` and `face_attended_backend.spec` for build configurations.

## 🖥️ Running on GPU

To enable GPU acceleration (NVIDIA):

1. Install CUDA Toolkit and cuDNN (compatible with your GPU).
2. Replace `onnxruntime` with `onnxruntime-gpu` in `requirements.txt` and run:

```bash
pip install onnxruntime-gpu
```

3. In your code, set ONNX to use CUDA:

```python
import onnxruntime as ort
session = ort.InferenceSession('model.onnx', providers=['CUDAExecutionProvider'])
```

4. Verify GPU usage with `nvidia-smi`.

## 📝 Contributing

Pull requests and issues are welcome! Please follow standard Python and Node.js style guides. See `.gitignore` for files to exclude from commits.

## 📄 License

This project is licensed under the AGPL-3.0 License. See the LICENSE file for details.

## 🌐 Repository Structure

This repository contains both backend (server/) and frontend (front/) code. See each folder for specific README and setup instructions.
