import sys
import cv2
import importlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

rec_mod = importlib.import_module('04_plate_ocr.recognizers')
prep_mod = importlib.import_module('04_plate_ocr.preprocess')
norm_mod = importlib.import_module('04_plate_ocr.normalization')
gram_mod = importlib.import_module('04_plate_ocr.grammar')

get_recognizer = rec_mod.get_recognizer
preprocess_crop = prep_mod.preprocess_crop
normalize_plate_text = norm_mod.normalize_plate_text
score_indian_grammar = gram_mod.score_indian_grammar
generate_grammar_alternatives = gram_mod.generate_grammar_alternatives


def test_single_crop(image_path: str, variant: str = 'gray'):
    img = cv2.imread(image_path)
    if img is None:
        print(f'[ERROR] Could not load image from: {image_path}')
        return

    rec = get_recognizer('easyocr_crnn', device='cuda')
    prep_img, meta = preprocess_crop(img, variant=variant)

    raw_text, conf, chars = rec.recognize(prep_img)
    norm_text = normalize_plate_text(raw_text)
    gram_sc = score_indian_grammar(norm_text)
    alts = generate_grammar_alternatives(norm_text)

    print(f'================ OCR SINGLE CROP TEST ================')
    print(f'Image Path:           {image_path}')
    print(f'Preprocessing:        {variant}')
    print(f'Raw OCR Text:         \"{raw_text}\"')
    print(f'Normalized Plate:     \"{norm_text}\"')
    print(f'OCR Confidence:       {conf:.4f}')
    print(f'Grammar Score:        {gram_sc:.4f}')
    print(f'Grammar Alternatives: {alts}')
    print('======================================================')


if __name__ == '__main__':
    val_imgs = list((ROOT_DIR / 'datasets' / 'plate_ocr' / 'images' / 'val').glob('*.jpg'))
    sample_path = str(val_imgs[0]) if val_imgs else ''
    if sample_path:
        test_single_crop(sample_path)
    else:
        print('No sample image found.')
