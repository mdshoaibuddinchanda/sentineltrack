# Final Model Selection

Selection is based on measured evidence, not parameter count:

- OCR: PP-OCRv5 mobile remains selected for the balanced profile because its expanded-validation exact ties server after postprocessing while retaining substantially lower latency and better character accuracy/CER.
- Temporal: current voter with a 5-frame window is the balanced operational choice; 8-frame current voter has the highest measured exact on its smaller eligible subset.
- P3: the authoritative clean-data YOLO11s candidate is selected over production when its locked-test evaluation is present; otherwise selection remains pending.
- P1: retain YOLO11m vehicle model as operational baseline until a real vehicle GT corpus is supplied.
