# Phase 7: Pydantic & Strict Validation

As we shift into **Part 2: Security, Data, & Payload Handling**, our first priority is defending the AI models from malformed data.

If your frontend sends a broken image string, or forgets to include a bounding box, you do not want your `scrfd_10g.onnx` model to crash midway through matrix multiplication. Phase 7 explains how Pydantic acts as an impenetrable shield for your backend.

## The Goal

Understand how `api/schemas.py` uses Pydantic to strictly validate every byte of incoming JSON data before it even reaches your Python route functions.

---

### Step 1: The Raw JSON Threat

When a student scans their face, your mobile app or frontend sends an HTTP POST request carrying raw text (JSON).

```json
{
  "image": "base64_data...",
  "bbox": [15, 20, 100, 100]
}
```

In traditional backends, developers have to write messy `if` statements to manually verify that "bbox" exists and contains exactly 4 numbers. If they forget, the server crashes with a `KeyError` or `IndexError`.

### Step 2: The Pydantic Shield

Look at `server-vino/api/schemas.py`. Here is how FastAPI solves this automatically:

```python
class FaceRecognitionRequest(BaseModel):
    image: str
    bbox: List[float]
    landmarks_5: Optional[List[List[float]]] = None
    group_id: Optional[str] = None
    enable_liveness_detection: bool = True
```

This is not a normal Python class; it is a **Pydantic BaseModel**. It is a strict contract.

When the raw JSON hits your server, Pydantic intercepts it and attempts to force the data into this exact shape:

1. `image` **MUST** be a string.
2. `bbox` **MUST** exist, and it **MUST** be a List containing floating-point numbers.
3. `landmarks_5` is **Optional**. If the frontend sends it, it must be a nested list of floats. If they don't send it, Pydantic safely defaults it to `None`.
4. `enable_liveness_detection` **MUST** be a boolean (True/False). If the frontend doesn't send it, Pydantic defaults it to `True`.

### Step 3: Graceful Bouncing (The 422 Error)

What happens if the frontend sends `enable_liveness_detection: "yes"` instead of a boolean `true`?

In many frameworks, this would trigger an internal `TypeError` and tracebacks in your logs.
Instead, Pydantic immediately rejects the request at the network boundary. Your Python route function _never even executes_.

FastAPI instantly sends a clean `HTTP 422 Unprocessable Entity` error back to the frontend:

```json
{
  "detail": [
    {
      "loc": ["body", "enable_liveness_detection"],
      "msg": "value could not be parsed to a boolean",
      "type": "type_error.bool"
    }
  ]
}
```

The frontend developer instantly knows exactly what they did wrong.

### Step 4: The Python Benefit (IntelliSense)

Because you mapped the JSON to a strict Python object, your editor (VS Code, etc.) is fully aware of the data type.
Inside your route in `recognition.py`:

```python
if request.enable_liveness_detection:
    # Do liveness check
```

If you accidentally type `request.enable_Liveness`, your Python editor will immediately show a red squiggly line because it mathematically knows `enable_Liveness` does not exist on the `FaceRecognitionRequest` model.

---

### Phase 7 Summary

1. Unvalidated JSON is the #1 cause of API server crashes.
2. `api/schemas.py` defines strict Pydantic contracts for every single API endpoint.
3. If data is missing or incorrectly typed, the server automatically bounces it with a `422` error before your AI code ever runs.
4. If the data is perfect, your Python route functions are guaranteed safe execution with full editor auto-completion.
