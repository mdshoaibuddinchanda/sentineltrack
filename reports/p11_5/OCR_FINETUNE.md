# OCR Fine-Tuning

Status: INTERRUPTED_RESOURCE_LIMITED_NO_CHECKPOINT.

One and only one bounded official PP-OCRv5_mobile_rec real-only attempt was made in the separate `sentinel_ocr_paddle` environment. The run was stopped after the first CPU logging interval remained silent for approximately six minutes; no model checkpoint, validation metric, export, or locked-test read was produced. No 25% synthetic follow-up was started because the required A gate did not produce an improvement result.

| Field | Recorded value |
|---|---|
| Environment | sentinel_ocr_paddle; Python 3.10.21; Windows CPU |
| Packages | PaddlePaddle 3.3.1; PaddleOCR 3.7.0; PaddleX 3.7.2 |
| Official source | PaddleOCR commit `2661c7c0ef5c613e8f93c6e93b2e052399f0f854` |
| Pretrained source | PP-OCRv5_mobile_rec_pretrained.pdparams; SHA256 `04745475b97a1faf029c7442a4c4421b156249b9395814e509bf4a9804e37750` |
| Data | real-only; train 1,382; val 147; locked test 178 held out |
| Config | official `configs/rec/PP-OCRv5/PP-OCRv5_mobile_rec.yml`, bounded to 1 epoch, batch 8, Adam, Cosine LR 0.0005, CPU, workers 0 |
| Checkpoint / best val / export SHA | not produced |
| Metrics | raw exact, postprocessed exact, character accuracy, CER, grammar, empty-read, P50/P95, crops/s: not available because training produced no checkpoint |

The existing PP-OCRv5 Mobile ONNX artifact remains selected and the locked zero-shot tournament result remains the authoritative OCR evidence. The isolated environment and official source were not added to the production dependency graph.
