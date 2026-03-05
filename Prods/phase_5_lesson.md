# Phase 5: FastAPI Routing & Request State

Continuing from our Comprehensive Production-Ready Learning Roadmap. Phase 5 focuses on how FastAPI maps URLs to functions and manages global application state (like your heavy AI models) during high-traffic request routing.

## The Goal

Understand how `api/routes/` works. Learn how FastAPI extracts data from incoming HTTP requests and passes app-level state seamlessly down to the specific route handlers.

---

### Step 1: The APIRouter Aggregation

Look at `server-vino/api/endpoints.py`.

In a production application, you cannot put all your endpoints into a single `main.py` file. It becomes unmaintainable. FastAPI solves this using the `APIRouter` class.

Instead of defining endpoints directly on the main `app`, you create separate routers for different domains:

```python
router.include_router(detection.router, tags=["detection"])
router.include_router(recognition.router, tags=["recognition"])
router.include_router(attendance.router, tags=["attendance"])
```

This is a switchboard. When a request comes in for `/face/recognize`, this file tells FastAPI to forward the traffic entirely to the `recognition.router`.

### Step 2: Route Decorators & Pydantic Validation

Look at `server-vino/api/routes/recognition.py`.

Here is the actual destination for the traffic:

```python
@router.post("/face/recognize", response_model=FaceRecognitionResponse)
async def recognize_face(request: FaceRecognitionRequest):
```

1. **The Decorator (`@router.post`)**: This line tells FastAPI that this specific Python function is triggered by an HTTP POST request to `/face/recognize`.
2. **The Request Definition (`request: FaceRecognitionRequest`)**: This is the magic of FastAPI. `FaceRecognitionRequest` is a Pydantic strict model. Before this python function ever runs, FastAPI reads the incoming JSON payload and forces it through the Pydantic model rules. If the frontend sent bad JSON, FastAPI instantly rejects it with a `422 Unprocessable Entity` error. Your python logic is completely protected from malformed data.

### Step 3: Managing Global State (Dependency Injection)

In a face recognition server, the ONNX AI models (like `scrfd_10g.onnx`) are massive. You cannot load them from the hard drive every time a student scans their face—it would take seconds per request.

Instead, they are loaded exactly once when the server boots, and stored in the "Global State". But how do the route functions access them?

Look at the function arguments again:

```python
async def recognize_face(
    request: FaceRecognitionRequest,
    face_recognizer=Depends(get_face_recognizer),
):
```

This is **Dependency Injection**. The function explicitly says "I depend on the Face Recognizer to do my job".

When FastAPI routes a request to this function, it automatically executes `get_face_recognizer()` (which safely fetches the model from RAM) and injects it into the function as the `face_recognizer` variable. The routing logic remains completely separated from the AI initialization logic.

---

### Phase 5 Summary

1. `endpoints.py` acts as a traffic control switchboard.
2. `@router.post` connects a specific URL to a python function.
3. Pydantic guarantees the incoming data is strictly typed before the function executes.
4. Dependency Injection guarantees the function has access to the pre-loaded AI models sitting in the global server RAM.
