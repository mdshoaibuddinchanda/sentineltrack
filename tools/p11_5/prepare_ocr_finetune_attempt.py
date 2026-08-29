"""Prepare one isolated, real-only PP-OCRv5 mobile-recognition run.

This helper never rewrites the frozen OCR dataset. It creates absolute-path
label lists and a bounded one-epoch official PaddleOCR config under the ignored
P11.5 run directory; the official repository's ``tools/train.py`` is invoked
separately inside the dedicated ``sentinel_ocr_paddle`` environment.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets" / "plate_ocr"
RUN_DIR = ROOT / "runs" / "p11_5" / "ocr_finetune" / "real_only"


def build_label_list(split: str, destination: Path) -> int:
    labels_dir = DATASET / "labels" / split
    images_dir = DATASET / "images" / split
    rows: list[str] = []
    for label_path in sorted(labels_dir.glob("*.txt")):
        image_path = images_dir / f"{label_path.stem}.jpg"
        if not image_path.is_file():
            raise FileNotFoundError(f"missing image for {label_path}")
        text = label_path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"empty OCR label: {label_path}")
        rows.append(f"{image_path.resolve()}\t{text}\n")
    destination.write_text("".join(rows), encoding="utf-8")
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    args = parser.parse_args()

    official_root = args.official_root.resolve()
    checkpoint = args.checkpoint.resolve()
    source_config = official_root / "configs" / "rec" / "PP-OCRv5" / "PP-OCRv5_mobile_rec.yml"
    dictionary = official_root / "ppocr" / "utils" / "dict" / "ppocrv5_dict.txt"
    if not source_config.is_file():
        raise FileNotFoundError(source_config)
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    if not dictionary.is_file():
        raise FileNotFoundError(dictionary)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    train_list = RUN_DIR / "train_list.txt"
    val_list = RUN_DIR / "val_list.txt"
    train_count = build_label_list("train", train_list)
    val_count = build_label_list("val", val_list)

    config = yaml.safe_load(source_config.read_text(encoding="utf-8"))
    global_config = config["Global"]
    global_config.update(
        {
            "use_gpu": False,
            "distributed": False,
            "epoch_num": 1,
            "print_batch_step": 25,
            "save_epoch_step": 1,
            "eval_batch_step": [0, 1000000],
            "save_model_dir": str(RUN_DIR.resolve()),
            "pretrained_model": str(checkpoint),
            "checkpoints": None,
            "character_dict_path": str(dictionary),
            "infer_mode": False,
        }
    )
    train = config["Train"]
    train["dataset"]["data_dir"] = ""
    train["dataset"]["label_file_list"] = [str(train_list.resolve())]
    train["sampler"]["first_bs"] = 8
    train["sampler"]["fix_bs"] = True
    train["loader"]["batch_size_per_card"] = 8
    train["loader"]["num_workers"] = 0
    config["Eval"]["dataset"]["data_dir"] = ""
    config["Eval"]["dataset"]["label_file_list"] = [str(val_list.resolve())]
    config["Eval"]["loader"]["batch_size_per_card"] = 8
    config["Eval"]["loader"]["num_workers"] = 0

    config_path = RUN_DIR / "config.yml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    shutil.copy2(source_config, RUN_DIR / "official_source_config.yml")
    print(f"run_dir={RUN_DIR}")
    print(f"config={config_path}")
    print(f"train_count={train_count}")
    print(f"val_count={val_count}")
    print(f"checkpoint={checkpoint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
