# End-to-End Report

Pipeline: detector → predicted crop → PP-OCRv5 mobile → existing structural decoder metrics on strict real test.

| model | det R | OCR matched | E2E exact | E2E CER | P50 ms | P95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| models/plate/production/best.pt | 0.948805 | 278 | 0.099 | 3.8947 | 25.631 | 70.828 |
| runs/p11_5/p3-yolo11s-v2-e20-b4-640-r3-clean/weights/best.pt | 0.972696 | 285 | 0.0956 | 4.0444 | 25.095 | 33.3 |

P5 safety FPR is unavailable because the strict plate test contains positive plate objects only and no negative vehicle/background GT.
