# Phase 13: ONNX Anatomy & InferenceSessions

In Phase 12, we mathematically squished and stretched our image into a normalized Tensor `(1, 3, 640, 640)`.
In Phase 13, we finally feed that Tensor to the AI.

I have created a sandbox script for you at `a:\FILES\py\BBFA\server-vino\sandbox\phase_13_sandbox.py`. This script natively loads the `scrfd_10g.onnx` weights into RAM and mathematically interrogates the AI model to see exactly what shape it expects.

## The Goal

Understand what an `InferenceSession` is, how the computational graph is structured, and what mathematical shapes the ONNX Face Detector demands.

---

### Step 1: The InferenceSession

When your FastAPI server boots up, it essentially runs this line of code:

```python
session = ort.InferenceSession("weights/scrfd_10g.onnx", providers=['CPUExecutionProvider'])
```

The `scrfd_10g.onnx` file is 16 Megabytes on your hard drive. It is a frozen "Computational Graph" containing millions of pre-trained mathematical weights.
Creating an `InferenceSession` reads that 16MB file and explicitly loads the entire mathematical graph into your server's CPU Random Access Memory (RAM).

**Critical Production Rule**: You must _never_ create an `InferenceSession` inside a FastAPI `@router.post` endpoint. If you did, your server would waste 0.5 seconds re-loading the 16MB file from the hard drive every single time a student scanned their face. The `InferenceSession` must be created exactly once at boot (Global State).

### Step 2: Interrogating the Input Graph

If you run the sandbox script, it interrogates the ONNX session to find out what tensor shape the model expects:

```
Input 0: Name='input.1'
         Required Shape: [1, 3, '?', '?']
         Required Data Type: tensor(float)
```

This output is incredibly revealing:

1.  **`1`**: It expects a Batch size of 1.
2.  **`3`**: It expects 3 Color Channels (The C in NCHW).
3.  **`?` and `?`**: Notice the Height and Width are question marks! This specific SCRFD model was incredibly well-engineered. It supports **Dynamic Shapes**. You don't _strictly_ have to provide `640x640`. You can provide `480x480` or `1280x1280` and the neural network will mathematically adapt! (However, consistent `640x640` is safer for memory consistency).
4.  **`tensor(float)`**: Exactly as we did in Phase 12, it demands normalized decimal floats, not `0-255` integers.

### Step 3: Interrogating the Output Tensors

Once the AI does its matrix multiplication, what does it push out?
If you run the script, it reveals **9 Output Tensors**:

```
Output 0: Name='448' - Shape: [12800, 1]
...
Output 3: Name='451' - Shape: [12800, 4]
...
Output 6: Name='454' - Shape: [12800, 10]
...
```

Why so many outputs? Modern face detectors use "Feature Pyramids". They look for faces at 3 different scales (Small, Medium, Large).
For each of the 3 scales, the AI outputs 3 distinct arrays:

1.  **Objectness Score `[..., 1]`**: "I am X% confident this cluster of pixels is a face."
2.  **Bounding Box `[..., 4]`**: The (X, Y, Width, Height) coordinates of the face.
3.  **Landmarks `[..., 10]`**: The 5 point geometry (Left Eye, Right Eye, Nose, Left Mouth, Right Mouth) used for alignment, with X and Y coords for each point (5 \* 2 = 10).

_(3 Scales) x (3 Data Types) = 9 Tensors!_

---

### Phase 13 Summary

1.  `InferenceSession` loads the AI's math graph directly into fast server RAM.
2.  The ONNX model explicitly validates that the incoming tensor shape matches `[1, 3, Height, Width]`.
3.  The model outputs 9 separate multi-dimensional math arrays containing raw mathematical coordinates outlining where it suspects faces might be.
