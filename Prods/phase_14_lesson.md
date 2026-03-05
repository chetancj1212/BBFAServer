# Phase 14: Parsing Detector Outputs & NMS

In Phase 13, we saw that the `scrfd_10g.onnx` Face Detector model mathematically outputs 9 dense arrays, representing over 16,000 potential bounding boxes per image.

Why 16,000 possibilities? Because neural networks are statistical guessers. When looking at a student's face, the AI doesn't draw one box. It draws 50 slightly different boxes around the exact same face, each with varying confidence scores (e.g., 99%, 85%, 72%).

If we sent all 50 boxes to the recognition engine, your server would crash trying to authenticate the same student 50 times simultaneously. We must clean up the AI's messy output using an algorithm called **Non-Maximum Suppression (NMS)**.

I wrote a sandbox script to physically demonstrate this math at `a:\FILES\py\BBFA\server-vino\sandbox\phase_14_sandbox.py`.

## The Goal

Understand the mathematical concept of Intersection over Union (IoU) and how the NMS algorithm filters out duplicate face detections.

---

### Step 1: Intersection over Union (IoU)

Before we can delete duplicate boxes, we need a mathematical formula to determine _if two boxes are looking at the same object_.

**IoU** is the ratio of two boxes' intersecting area divided by their combined total area.

- If `Box A` and `Box B` do not touch at all, IoU = 0.0.
- If `Box A` and `Box B` perfectly overlap, IoU = 1.0.
- If `Box A` and `Box B` overlap significantly (e.g., measuring the same face), IoU > 0.5.

### Step 2: Sorting by Confidence

The ONNX model assigns a confidence score to every proposed box.
In the sandbox script, we simulated 4 boxes. Three boxes surrounded the true face, and one boxed an object in the background.

```
Box 0: Confidence 0.95
Box 1: Confidence 0.88
Box 2: Confidence 0.75
Box 3: Confidence 0.40 (Background object)
```

The very first step of NMS is to sort all 16,000 raw predictions from Highest score to Lowest score.

### Step 3: The Suppression Loop

Now we execute the core algorithm:

1.  **Select the Best**: We look at the top array. We instantly confirm `Box 0 (Score: 0.95)` as a True Face. We keep it permanently.
2.  **Compare downwards**: We iterate through every other box in the list (`Box 1`, `Box 2`, `Box 3`) and calculate the **IoU** against our confirmed `Box 0`.
3.  **Suppress**:
    - `Box 1` significantly overlaps `Box 0` (IoU = 0.8). It's a duplicate. Delete it!
    - `Box 2` significantly overlaps `Box 0` (IoU = 0.6). It's a duplicate. Delete it!
    - `Box 3` is in the background and doesn't overlap `Box 0` at all (IoU = 0.0). Keep it in the queue.
4.  **Repeat**: Move to the next highest remaining box in the queue (`Box 3`). Confirm it as a True Face, and compare it against any remaining boxes.

### Step 4: The Final Output

By the end of the loop, the 16,000 raw, messy ONNX outputs have been ruthlessly pruned down to exactly the number of distinct human faces in the camera frame.

By applying NMS, we transformed raw AI probabilities into clean, usable `(X, Y, Width, Height)` integer coordinates.

---

### Phase 14 Summary

1.  Face detectors predict thousands of overlapping redundant boxes around a single face.
2.  **IoU** mathematically measures how much two boxes overlap (0.0 to 1.0).
3.  **NMS** sorts boxes by confidence and deletes overlapping boxes (IoU > 0.4) because they are mathematically proven to be redundant guesses.
4.  The final result is a clean array containing exactly one perfect bounding box per human face perfectly suited for the Recognition stage.
