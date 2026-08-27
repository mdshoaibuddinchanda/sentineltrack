import sys
import importlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

eval_mod = importlib.import_module('04_plate_ocr.training.evaluate')
rec_mod = importlib.import_module('04_plate_ocr.recognizers')

get_recognizer = rec_mod.get_recognizer
run_full_evaluation = eval_mod.run_full_evaluation
run_preprocessing_ablation = eval_mod.run_preprocessing_ablation
run_derived_multiframe_stress_test = eval_mod.run_derived_multiframe_stress_test


def main():
    rec = get_recognizer('easyocr_crnn', device='cuda')
    print('================ RUNNING PRIORITY 4 REAL EVALUATION SUITE ================')
    run_preprocessing_ablation(rec)
    run_full_evaluation(rec, split='val', variant='gray')
    run_full_evaluation(rec, split='test', variant='gray')
    run_derived_multiframe_stress_test(rec, split='test')
    print('==========================================================================')


if __name__ == '__main__':
    main()
