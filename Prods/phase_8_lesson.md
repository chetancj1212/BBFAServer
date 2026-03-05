# Phase 8: Handling Binary Data (Multi-Part Forms)

We continue **Part 2: Security, Data, & Payload Handling**.

In most of our face recognition endpoints, the frontend sends the image as a Base64 encoded string inside a JSON payload (as we saw in Phase 4). However, Base64 strings are ~33% larger than raw binary files, which wastes network bandwidth.

If a student uploads a 5MB high-resolution selfie, sending it as JSON is incredibly inefficient. This is where **Multi-Part Form Data** and binary streams come in.

## The Goal

Understand how to bypass JSON entirely and accept raw binary streams securely using FastAPI's `UploadFile`.

---

### Step 1: The Binary Route

Look at `server-vino/api/routes/detection.py` around line 120.

```python
@router.post("/detect/upload")
async def detect_faces_upload(
    file: UploadFile = File(...),
    model_type: str = "face_detector",
):
```

Instead of `request: DetectionRequest` (which triggers JSON parsing), this endpoint uses `file: UploadFile`.

When the frontend hits this route with a `multipart/form-data` request, FastAPI completely skips the JSON parser. It treats the payload as a raw binary stream of 1s and 0s directly from the student's camera.

### Step 2: The UploadFile Object (Spooling)

Why use `UploadFile` instead of standard Python `bytes`?

Imagine a malicious user tries to upload a fake 10-Gigabyte image to crash your server's RAM.
If you used standard bytes, FastAPI would try to load all 10GB into RAM at once, crashing your Intel i5 instantly.

**UploadFile uses a "Spooled File".**
FastAPI loads the first 1 Megabyte of the image into RAM. If the file is larger than 1MB, FastAPI stops using RAM and safely buffers the rest of the bytes directly to a temporary file on your hard drive. Your server memory is completely protected from massive file uploads.

### Step 3: Await the Stream

```python
contents = await file.read()
```

Because `UploadFile` is reading from a file stream (or hard drive buffer), it takes time. In Phase 6, we talked about multi-worker concurrency.

Notice the `await` keyword. While this specific worker is waiting 0.5 seconds for the 5MB image to finish downloading from the student's slow mobile network, the `await` keyword effectively tells the python worker: _"Hey, go help another student log in while I wait for this download to finish."_

This is the power of asynchronous Python (`async def`).

### Step 4: The Immediate Decode

```python
nparr = np.frombuffer(contents, np.uint8)
image_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
```

Once the binary bytes are fully downloaded into the `contents` variable, we bypass Base64 decoding entirely.

We immediately drop the raw bytes into a NumPy 1D array (`np.frombuffer`), and then tell OpenCV to reconstruct the 3-Dimensional `image_bgr` Tensor.

---

### Phase 8 Summary

1. Base64 JSON strings are inefficient for large images.
2. `UploadFile` accepts raw binary streams, reducing network payload size by 33%.
3. `UploadFile` protects your server RAM by buffering massively large files to the local hard drive (Spoof Protection).
4. `await file.read()` prevents slow mobile uploaders from blocking other students on your server.
5. We skip Base64 decoders and feed the raw bytes directly to OpenCV.
