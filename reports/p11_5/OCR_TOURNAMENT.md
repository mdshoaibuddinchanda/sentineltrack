# OCR Tournament

Ranking uses full-string exact accuracy first on legacy validation; expanded validation tests robustness; locked test is a final read-only readout.

| candidate | split | exact post | char post | CER post | P50 ms | P95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| ppocr_mobile | legacy_val | 0.6463 | 0.8465 | 0.1064 | 10.023 | 17.301 |
| ppocr_mobile | expanded_val | 0.6533 | 0.8497 | 0.1042 | 10.248 | 19.342 |
| ppocr_mobile | locked_test | 0.5787 | 0.7839 | 0.1557 | 9.33 | 16.26 |
| ppocr_server | legacy_val | 0.6463 | 0.7944 | 0.147 | 460.103 | 611.752 |
| ppocr_server | expanded_val | 0.6533 | 0.7986 | 0.1441 | 468.011 | 585.855 |
| ppocr_server | locked_test | 0.5787 | 0.7721 | 0.1652 | 442.15 | 671.762 |
| easyocr_rec_only | legacy_val | 0.0272 | 0.2006 | 0.3769 | 35.211 | 73.106 |
| easyocr_rec_only | expanded_val | 0.04 | 0.2105 | 0.3706 | 36.654 | 73.207 |
| easyocr_rec_only | locked_test | 0.0618 | 0.2155 | 0.386 | 32.677 | 73.472 |

Unavailable modern candidates are listed in the support matrix inside ocr_tournament.json; no score is claimed for missing implementations or weights.
