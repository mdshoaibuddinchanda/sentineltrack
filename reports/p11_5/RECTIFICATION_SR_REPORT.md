# Rectification / Enhancement / SR Report

Measured PP-OCRv5 mobile over margins 0/2/4/6/8 and raw, CLAHE, sharpen, conservative rectification, and classical Lanczos x2.

Best legacy-validation configuration by postprocessed exact: margin=0, variant=raw, exact=0.6463.
Best locked-test configuration by postprocessed exact: margin=0, variant=rectify, exact=0.5899.

The x2 row is a classical resize proxy, not a learned SR claim. False-correction risk is represented by raw-vs-postprocessed exact deltas; inspect the JSON for all aggregate rows.
