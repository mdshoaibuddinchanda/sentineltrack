# Synthetic Ablation

Corpus status: SYNTHETIC_GENERATED_NOT_AUTHORITATIVE_TEST; count: 100000; target: 100,000.
Screen status: COMPLETE_WITH_SCREENING_OR_BLOCKERS; protocol: same candidate initialization; 3-epoch isolated real-only, +25%, +50% synthetic train screens; real strict val/test retained.

| ablation | status | real train | synthetic train | P | R | F1 | mAP50 | mAP50-95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| real_only_screen_e3 | COMPLETE | 500 | 0 | 0.977871 | 0.980328 | 0.979098 | 0.991525 | 0.732293 |
| real_plus_synthetic_25pct_screen_e3 | COMPLETE | 500 | 125 | 0.98297 | 0.960656 | 0.971685 | 0.989597 | 0.726403 |
| real_plus_synthetic_50pct_screen_e3 | COMPLETE | 500 | 250 | 0.981588 | 0.970492 | 0.976009 | 0.989104 | 0.698319 |

The bounded screening is evidence only: all three candidates used the same initialization and real strict validation/test splits. Synthetic images are not authoritative test data and are ignored by Git. A full-scale 100,000-example training run remains intentionally unclaimed until compute/time and a promotion gate are available.
The manifest records states/BH-series, plate styles, four severity bands, multiple local font proxies, and degradation coverage including perspective, blur, downsample, noise, JPEG/video compression, exposure, glare, shadow, rain, fog, dirt, screws, occlusion, color shift, contrast, and night.
