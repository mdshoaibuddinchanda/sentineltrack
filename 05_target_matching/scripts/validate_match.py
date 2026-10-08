import sys
import argparse
import importlib

scorer_mod = importlib.import_module('05_target_matching.scorer')
norm_mod = importlib.import_module('05_target_matching.normalizer')
TargetMatchScorer = scorer_mod.TargetMatchScorer
normalize_target_registration = norm_mod.normalize_target_registration


def main():
    parser = argparse.ArgumentParser(description='Compare Target Registration vs Observed OCR')
    parser.add_argument('target', type=str, help='Target registration number (e.g. GJ01AB1234)')
    parser.add_argument('observed', type=str, help='Observed OCR string (e.g. GJ01A81234)')
    parser.add_argument('--conf', type=float, default=0.90, help='OCR confidence score [0.0, 1.0]')
    parser.add_argument('--support', type=int, default=3, help='Multi-frame support count')

    args = parser.parse_args()

    norm_target, ok_t, err_t = normalize_target_registration(args.target)
    norm_obs, ok_o, err_o = normalize_target_registration(args.observed)

    if not ok_t:
        print(f'Error in target: {err_t}')
        sys.exit(1)
    if not ok_o:
        print(f'Error in observed: {err_o}')
        sys.exit(1)

    scorer = TargetMatchScorer()
    res = scorer.score_match(
        target_id='cli-tgt',
        target_registration=norm_target,
        observed_registration=norm_obs,
        ocr_confidence=args.conf,
        multi_frame_support=args.support
    )

    print('============================================================')
    print('SENTINELTRACK PRIORITY 5 TARGET MATCH EVALUATION')
    print('============================================================')
    print(f'Target Registration:    {args.target} -> {norm_target}')
    print(f'Observed Registration:  {args.observed} -> {norm_obs}')
    print(f'Match Score:            {res.match_score:.4f}')
    print(f'Match Class:            {res.match_class.value}')
    print(f'Exact Match:            {res.exact_match}')
    print(f'Raw Edit Distance:      {res.raw_distance}')
    print(f'Confusion Distance:     {res.confusion_distance:.2f}')
    print('------------------------------------------------------------')
    print('Explainability Reasons:')
    for r in res.reasons:
        print(f'  • {r}')
    print('============================================================')


if __name__ == '__main__':
    main()
