# Synthetic Ablation

Corpus status: SYNTHETIC_GENERATED_NOT_AUTHORITATIVE_TEST; count: 100000; target: 100,000.
Screen status: COMPLETE_WITH_SCREENING_OR_BLOCKERS; protocol: same candidate initialization; 3-epoch isolated real-only, +25%, +50% synthetic train screens; real strict val/test retained. Decision: REJECTED_BY_BOUNDED_SCREEN.

| ablation | status | real train | synthetic train | P | R | F1 | mAP50 | mAP50-95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| real_only_screen_e3 | COMPLETE | 500 | 0 | 0.977871 | 0.980328 | 0.979098 | 0.991525 | 0.732293 |
| real_plus_synthetic_25pct_screen_e3 | COMPLETE | 500 | 125 | 0.98297 | 0.960656 | 0.971685 | 0.989597 | 0.726403 |
| real_plus_synthetic_50pct_screen_e3 | COMPLETE | 500 | 250 | 0.981588 | 0.970492 | 0.976009 | 0.989104 | 0.698319 |

Decision: `REJECTED_BY_BOUNDED_SCREEN`. The real-only screen was the best measured option (F1 0.979098; mAP50-95 0.732293); adding 25% or 50% synthetic data reduced mAP50-95 to 0.726403 and 0.698319. Synthetic images are not authoritative test data and are ignored by Git. No full-scale 100,000-example training run is required for the P11.5 freeze.
The manifest records states/BH-series, plate styles, four severity bands, multiple local font proxies, and degradation coverage including perspective, blur, downsample, noise, JPEG/video compression, exposure, glare, shadow, rain, fog, dirt, screws, occlusion, color shift, contrast, and night.
