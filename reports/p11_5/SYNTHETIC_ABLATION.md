# Synthetic Ablation

Corpus status: `SYNTHETIC_GENERATED_NOT_AUTHORITATIVE_TEST`; count: 100,000; target: 100,000.

The isolated screening used the same P11.5 candidate initialization, three epochs, batch 1, 640px input, a deterministic lexicographic 500-image real-train subset, and the full real strict V2 validation/test. It stages only hard links/copies under an ignored directory; synthetic images and trial weights are not committed and do not replace the authoritative real-data model selection.

| ablation | test precision | test recall | test mAP50 | test mAP50-95 | note |
| --- | --- | --- | --- | --- | --- |
| real-only, 500 real | 0.977871 | 0.980328 | 0.991525 | 0.732293 | three-epoch screen |
| real + 125 synthetic (25%) | 0.982970 | 0.960656 | 0.989597 | 0.726403 | three-epoch screen |
| real + 250 synthetic (50%) | 0.981588 | 0.970492 | 0.989104 | 0.698319 | three-epoch screen |

The machine-readable result is `synthetic_screening.json`/`.csv`. In this pilot, adding synthetic data did not improve mAP50-95 over the real-only subset; the 25% mix had the best precision but lower recall, and the 50% mix had lower mAP50-95. This is not enough evidence to reject synthetic data at full scale, but it is enough not to promote it yet. The manifest records states/BH-series, plate styles, four severity bands, multiple local font proxies, and degradation coverage including perspective, blur, downsample, noise, JPEG/video compression, exposure, glare, shadow, rain, fog, dirt, screws, occlusion, color shift, contrast, and night.
