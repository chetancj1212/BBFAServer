# Phase 3: FastAPI Routing & Payload Validation

The incoming network request has survived the Cloudflare tunnel, Uvicorn workers, CORS, and Rate Limiting. Now, it finally enters your Python application logic.

How does FastAPI know _which_ Python function should handle a request to `https://api.chetancj.in/face/recognize`? And how does it guarantee the frontend didn't send broken data that will crash your AI?

## 1. The APIRouter (Traffic Control)

Look at `server-vino/api/endpoints.py` and `server-vino/api/routes/recognition.py`.

In a massive production backend, you cannot put 50 endpoints in a single `main.py` file. It becomes unreadable. Instead, FastAPI uses an **APIRouter**.

In `endpoints.py`, you can see traffic controller logic:

```python
router.include_router(detection.router, tags=["detection"])
router.include_router(recognition.router, tags=["recognition"])
router.include_router(attendance.router, tags=["attendance"])
```

This tells FastAPI: "If a request deals with face recognition, send it to the logic inside `routes/recognition.py`."

Inside `routes/recognition.py`, you see the exact destination:

```python
@router.post("/face/recognize", response_model=FaceRecognitionResponse)
async def recognize_face(request: FaceRecognitionRequest, ...):
```

The `@router.post` decorator tells FastAPI that this specific Python function `recognize_face` is the handler for any HTTP POST request that hits that specific URL.

## 2. Pydantic Schemas (The Bouncer)

Look at `server-vino/api/schemas.py`.

Before standard Python executes `recognize_face`, FastAPI intercepts the raw JSON payload and forces it through a **Pydantic Model** (in this case, `FaceRecognitionRequest`).

```python
class FaceRecognitionRequest(BaseModel):
    image: str  # Base64 encoded image
    bbox: List[float]  # Face bounding box [x, y, width, height]
    landmarks_5: Optional[List[List[float]]] = None
    group_id: Optional[str] = None
    enable_liveness_detection: bool = True
```

**Why is this critical for production?**
In old backend frameworks (like Flask or Express.js), you had to write 50 lines of `if` statements to check if the frontend sent the `bbox` array, if the `bbox` actually contained floats, and if the `image` was a string. If you forgot a check, your server would crash with a `KeyError` or `TypeError` midway through the AI math.

With Pydantic:

1. If the frontend forgets to send the `bbox` array, Pydantic immediately rejects the request with a `422 Unprocessable Entity` error.
2. If the frontend sends `enable_liveness_detection: "yes"` instead of `true`, Pydantic tries to cast it or rejects it.
3. Every single variable is guaranteed to be exactly the correct Python data type before your function ever runs.

## 3. Dependency Injection

Look back at the route definition:

```python
async def recognize_face(
    request: FaceRecognitionRequest,
    face_recognizer=Depends(get_face_recognizer),
    attendance_database: AttendanceDatabaseManager = Depends(get_attendance_db),
):
```

Notice `Depends(get_face_recognizer)`. This is FastAPI's **Dependency Injection** system.
The Web Server shouldn't know how to initialize AI models. Instead, when a request hits this endpoint, FastAPI automatically asks the Dependency system for the pre-loaded `face_recognizer` object from the server's memory and injects it directly into the function.

---

### Phase 3 Summary

1. The request enters `endpoints.py`, which routes the traffic to `recognition.py`.
2. Pydantic parses the raw JSON into strictly typed Python objects (`request.bbox`).
3. Dependency Injection grabs the heavy AI models from RAM and hands them to the function.

Now, we have clean data and loaded models. In Phase 4, we'll look at how we convert that Base64 string into a mathematical tensor that the ONNX model can actually understand!
