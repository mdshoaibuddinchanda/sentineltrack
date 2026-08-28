# P11.5 dataset report

## Intended use and grain

The inventory grain is one image/annotation record, with an explicit orphan
annotation record where an XML has no matching image. Detection records contain
image dimensions, class-0 plate boxes/polygons, split, hashes, source, license
status, and quality flags. OCR records contain one crop and its text label.
Video frames additionally carry an inferred sequence identifier. These records
are suitable for auditing and derivative-corpus construction; they are not a
substitute for a new labelled vehicle benchmark or a frame-level OCR track
benchmark.

## File structure and basic contents

```text
datasets/
├── archive.zip                         # 4,104 entries: 2,083 images + 2,021 YOLO labels
├── archive (1).zip                      # 3,396 entries: VOC/XML image collections
├── Indian plates/                      # original Roboflow export, 2,531 images
│   ├── train/images + labels            # 2,035 images
│   ├── valid/images + labels            # 329 images
│   ├── test/images + labels             # 167 images
│   ├── data.yaml                        # one class: IndianNumberPlate
│   └── README*.txt                      # source/export documentation
├── plate_detection/                    # frozen canonical detector dataset, 2,531 images
│   ├── images/{train,val,test}/         # 2,035 / 329 / 167
│   ├── labels/{train,val,test}/         # YOLO, class 0
│   ├── sources/real_public/             # source mirror; do not merge with canonical data
│   ├── sources/own/                     # currently empty
│   ├── sources/synthetic/               # currently empty
│   └── sources.csv                      # provenance for canonical records
├── plate_ocr/                          # frozen OCR crops, 1,707 JPG + 1,707 text labels
│   ├── images/{train,val,test}/         # 1,382 / 147 / 178
│   ├── labels/{train,val,test}/         # one text label per crop
│   ├── sources/                         # currently empty
│   ├── sources.csv                      # identity/crop/provenance metadata
│   └── README*.txt                      # source and ingestion notes
├── images/                              # archive image collection, 2,083 images
├── labels/                              # matching/partial YOLO labels, 2,021 files
├── google_images/                       # 442 images, 440 XML annotations
├── State-wise_OLX/                      # 602 images, 603 XML entries, 35 state/UT folders
├── video_images/                        # 654 frames + 654 XML annotations, 10 inferred sequences
└── experiments/
    ├── manifests/                       # generated source inventory and duplicate reports
    ├── plate_detection_v2/              # 5,281-image isolated derivative
    ├── plate_detection_obb_v1/          # 5,281-image OBB-label derivative, not trained
    ├── plate_ocr_v2/                    # 1,396 train / 150 val / 178 locked-test derivative
    └── synthetic_indian_v1/             # 8-example deterministic smoke corpus, not trained
```

The two archives remain in place. The extraction and audit did not rewrite the
frozen source directories.

## Audit evidence

| Check | Evidence | Interpretation |
|---|---:|---|
| Total inventory records | 13,082 | 13,081 image records plus one orphan XML record |
| Exact duplicate groups | 3,531 | Mostly intentional source mirrors/copies; deduplicate before mixing sources |
| Records in exact duplicate groups | 9,593 | 73.4% of inventory records are in an exact duplicate group |
| Near-duplicate candidate groups | 3,514 | pHash candidates require visual review before treating as independent evidence |
| Unlabeled images | 62 | Excluded from usable detection derivatives; do not invent labels |
| Invalid/quarantined records | 137 | Includes missing/empty labels, invalid geometry, orphan XML, and invalid plate text flags |
| Cross-split exact duplicate groups | 0 | Frozen canonical split hash check passed |
| Legacy OCR identity overlaps | 0 | Train/val/test identity leakage check passed |

Source-level usable counts:

- Frozen `plate_detection`: 2,530 usable detection records; one empty annotation.
- Frozen `plate_ocr`: all 1,707 crops have a non-empty OCR label; identity counts are train 675, val 144, test 144 with no overlap.
- `images_and_labels`: 2,021 usable detection records and 62 missing labels; three extension/byte-format mismatches are flagged.
- `google_images`: 442 usable detection records and 416 plate-text-valid XML names. Its `classes.txt` has mixed, non-one-class content and is not used as a class map.
- `State-wise_OLX`: 601 usable detection records, 581 valid plate-text names, one orphan XML, and one invalid box.
- `video_images`: 654 usable detection records, 633 valid plate-text names, and 654 sequence-capable frame records.

## Derivative datasets

Detection V2 contains 5,281 unique images from 6,248 usable candidates. The
canonical `plate_detection` split assignments are preserved. Exact copies of
`Indian plates` and `plate_detection_source_real_public` are excluded. Raw
sources are grouped by sequence, plate identity, or image hash before splitting.
All 5,281 images were hard-linked; source files were not rewritten.

OBB V1 has the same 5,281 images and split counts. Polygon annotations are
converted to minimum-area rectangles where available; axis-aligned boxes are a
fallback. No OBB model has been trained or promoted.

OCR V2 preserves the legacy 1,382/147/178 train/validation/test records by hard
link. It adds 14 train and 3 expanded-validation crops from validated VOC
records after legacy identity exclusion. The historical locked test is unchanged.
No OCR V2 model has been trained.

Synthetic V1 is currently an 8-example smoke corpus generated with seed 115,
covering white/yellow/green plates and easy/medium/hard/extreme/two-line
variants. It is a generator validation artifact, not an accuracy result.

## Quality risks and required follow-up

1. The exact-duplicate rate is high because the workspace contains the original
   export, the canonical copy, and a source mirror. Automated deduplication by
   SHA-256 and identity/sequence grouping must remain a pre-training gate.
2. The 62 unlabeled archive images, invalid boxes, orphan XML, and invalid plate
   names should remain quarantined until a human owner supplies corrections.
3. Source licensing is complete for the Roboflow CC-BY-4.0 export but remains
   unknown or unverified for several archive collections. These sources should
   not be used in a public submission until provenance is confirmed.
4. A vehicle-labelled evaluation corpus is still missing. P1 precision/recall,
   YOLO11-vs-YOLO26 tournament claims, and end-to-end vehicle recall therefore
   remain unevaluated.
