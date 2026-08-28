# P11.5 capacity and deployment delta

## Local measured evidence

The P3 detector artifact was measured on the local RTX 3050 with FP32, CUDA,
batch 1, and 640px input:

- p50: 14.883 ms
- p95: 17.492 ms
- throughput: 63.774 FPS
- safe camera capacity: not inferred

The OCR baseline was measured separately on ONNX Runtime CPU. Mobile measured
10.53 ms p50 / 24.85 ms p95 on the locked test probe; server measured 413.81 ms
p50 / 594.96 ms p95. These are crop-recognition timings, not complete
camera-stream timings.

## Cloud and multi-stream status

`cloud_balanced` and `cloud_accuracy` have no validated artifact and are
`UNAVAILABLE_NOT_BENCHMARKED`. No cloud machine was provisioned, so no cloud
latency, VRAM, throughput, or stream-capacity number is reported. A single-frame
detector probe is intentionally not converted into 1/5/10/25/50-stream safe
capacity.

The hardware benchmark tool records hardware ID, GPU, VRAM, model hash,
precision, batch, image size, p50, p95, throughput, and an explicit null when
safe capacity was not measured.
