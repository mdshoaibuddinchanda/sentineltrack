# P11.5 temporal report

`tools/p11_5/temporal.py` now provides a pure, test-covered weighted consensus
policy. It normalizes candidate strings, filters by confidence and crop
quality, aggregates support across frame indices, and returns an auditable
consensus result. It does not assert that a consensus is ground truth.

The source audit found 654 sequence-capable `video_images` frames across ten
inferred video IDs. Those XML annotations provide detection boxes and many
plate-like names, but there is no locked frame-level OCR track benchmark with a
defined train/validation/test protocol. Therefore current voter, best-3,
best-5, best-8, character fusion, logit fusion, learned fusion, quality-aware
escalation, and temporal promotion are `NOT_EVALUATED`.

Required evidence before promotion:

1. define track boundaries and frame order from the source video metadata;
2. validate frame-level text labels and identity grouping;
3. compare single-frame and each temporal policy on the same locked track set;
4. record exact match, character accuracy, CER, false-correction rate, and
   latency/VRAM under the intended stream load.
