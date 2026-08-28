# P11.5 OCR report

## Locked baseline comparison

Fresh evaluation used the frozen `datasets/plate_ocr` validation and locked test
sets. Metrics are postprocessed output unless stated otherwise.

| Model | Val exact | Val char accuracy | Val CER | Val p50/p95 ms | Test exact | Test char accuracy | Test CER | Test p50/p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| PP-OCRv5 mobile | 0.6463 | 0.8465 | 0.1064 | 10.92 / 25.50 | 0.5787 | 0.7839 | 0.1557 | 10.53 / 24.85 |
| PP-OCRv5 server | 0.6463 | 0.7944 | 0.1470 | 437.83 / 575.91 | 0.5787 | 0.7721 | 0.1652 | 413.81 / 594.96 |

Mobile is the current OCR baseline because it ties the server model on locked
test exact match, has higher test character accuracy, and is substantially
faster. Both are ONNX Runtime CPU measurements in this environment.

Raw-to-postprocessed mobile test exact match improved from 0.5000 to 0.5787;
that is a measured postprocessing result, not an independently trained model
gain. The server test changed from 0.5618 to 0.5787 after postprocessing.

## OCR V2 and challengers

OCR V2 has been constructed with identity exclusion and a preserved historical
test set, but it has not been fine-tuned or evaluated. SVTRv2, RepSVTR, PARSeq,
MGP-STR, and other challengers have no locally measured artifact/result in this
run. Fine-tuning and promotion remain open.
