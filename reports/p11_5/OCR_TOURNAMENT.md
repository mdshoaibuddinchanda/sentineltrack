# OCR Tournament

Ranking uses full-string exact accuracy first on legacy validation; expanded validation tests robustness; locked test is a final read-only readout.

| candidate | split | exact post | char post | CER post | P50 ms | P95 ms |
| --- | --- | --- | --- | --- | --- | --- |
| ppocr_mobile | legacy_val | 0.6463 | 0.8465 | 0.1064 | 9.705 | 16.758 |
| ppocr_mobile | expanded_val | 0.6533 | 0.8497 | 0.1042 | 9.57 | 14.646 |
| ppocr_mobile | locked_test | 0.5787 | 0.7839 | 0.1557 | 9.679 | 15.886 |
| ppocr_server | legacy_val | 0.6463 | 0.7944 | 0.147 | 446.159 | 631.095 |
| ppocr_server | expanded_val | 0.6533 | 0.7986 | 0.1441 | 431.418 | 558.217 |
| ppocr_server | locked_test | 0.5787 | 0.7721 | 0.1652 | 407.874 | 561.432 |
| easyocr_rec_only | legacy_val | 0.0272 | 0.2006 | 0.3769 | 29.602 | 62.95 |
| easyocr_rec_only | expanded_val | 0.04 | 0.2105 | 0.3706 | 32.238 | 64.815 |
| easyocr_rec_only | locked_test | 0.0618 | 0.2155 | 0.386 | 28.603 | 59.487 |

Unavailable modern candidates are listed in the support matrix inside ocr_tournament.json; no score is claimed for missing implementations or weights.
