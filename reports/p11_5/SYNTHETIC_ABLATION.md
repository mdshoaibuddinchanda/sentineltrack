# Synthetic Ablation

Corpus status: SYNTHETIC_GENERATED_NOT_AUTHORITATIVE_TEST; count: 100000; target: 100,000.

| ablation | status | note |
| --- | --- | --- |
| real_only | reference | real strict V2 |
| synthetic_to_real | not run | requires separate staged detector training |
| real_plus_synthetic_25pct | not run | requires ablation training |
| real_plus_synthetic_50pct | not run | requires ablation training |

Synthetic images are not authoritative test data and are ignored by Git. The manifest records states/BH-series, plate styles, four severity bands, multiple local font proxies, and degradation coverage including perspective, blur, downsample, noise, JPEG/video compression, exposure, glare, shadow, rain, fog, dirt, screws, occlusion, color shift, contrast, and night.
