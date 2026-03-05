# Phase 12: Image Normalization (HWC to NCHW Tensors)

Continuing **Part 3: Deep Learning Inference Mechanics (ONNX)**, we must address the problem of size and shape.

In Phase 11, OpenCV exploded our Raw Bytes into a 3-Dimensional `(1080, 1920, 3)` Tensor.
However, AI neural networks are mathematically rigid. The `scrfd_10g.onnx` face detector was historically trained on thousands of static `640x640` images.
If we feed it a `1920x1080` tensor, it will violently crash.

Worse, AI models expect their axes to be arranged in a radically different order than OpenCV.

I have created a sandbox script for you at `a:\FILES\py\BBFA\server-vino\sandbox\phase_12_sandbox.py` that practically demonstrates the exact algorithm your server uses. Let's break down the 4 steps of **Tensor Preprocessing**.

## The Goal

Understand how an OpenCV Tensor `[Height, Width, Color]` is mathematically stretched and rearranged into the normalized `[Batch, Color, Height, Width]` array that the ONNX Runtime demands.

---

### Step 1: Resizing

`resized_img = cv2.resize(image_bgr, (640, 640))`

Your student's frontal camera might capture images in 720p, 1080p, or 4K. To the AI, it does not matter. The first operation forcibly squashes the mathematical grid into a perfect `640x640` square.
_Note: In advanced facial detection, an "Affine Transform" or "Letterboxing" is preferred over naive resizing to prevent stretching the face vertically, but the destination shape is always 640x640._

### Step 2: Float Normalization

`normalized_img = resized_img.astype(np.float32) / 255.0`

OpenCV stores pixel intensities as integers from `0 to 255`.
Neural networks hate large numbers; large numbers cause "exploding gradients" during matrix multiplication.
We must divide every single one of the `640x640` pixels by `255.0` to mathematically strictly squish every data point to be a tiny fraction between `0.0` and `1.0`.

### Step 3: Axis Transposition (HWC to CHW)

`chw_tensor = np.transpose(normalized_img, (2, 0, 1))`

This is the most confusing part of Computer Vision.

- **OpenCV** arranges arrays as `[Height, Width, ColorChannels]`. A single pixel contains its Blue, Green, and Red data grouped together.
- **ONNX AI** demands `[ColorChannels, Height, Width]`.

We must use Numpy `transpose` to mathematically tear the image apart and re-stack it. The AI expects all 409,600 Blue pixels first, followed by all Green pixels, followed by all Red pixels.
The Tensor shape has transformed from `(640, 640, 3)` to `(3, 640, 640)`.

### Step 4: The Batch Dimension (NCHW)

`nchw_tensor = np.expand_dims(chw_tensor, axis=0)`

AI models are designed to operate on huge server farms (like a Cloudflare Datacenter) processing 64 images at the exact same time.
Even though your server is only processing **1** student's face right now, the AI still demands a "Batch" dimension at the very front of the array.

We use `np.expand_dims` to artificially shove a `1` at the front of the shape array.
The final mathematical shape of the Tensor is `(1, 3, 640, 640)`:

- `1`: (N) Number of Images in Batch
- `3`: (C) Color Channels
- `640`: (H) Height
- `640`: (W) Width

---

### Phase 12 Summary

1.  Neural networks are rigid and crash if input dimensions do not perfectly match their training data.
2.  OpenCV `[Height, Width, Channels]` (HWC) arrays must be aggressively reshaped.
3.  We divide pixels by 255.0 to normalize the math.
4.  We transpose the axes so Color explicitly comes first (CHW).
5.  We append a Batch dimension of 1 to the front because the Neural Network architecture demands it.
6.  The final `(1, 3, 640, 640)` math array is perfectly ready for `onnxruntime`.
