import sys
import argparse
import importlib

wl_mod = importlib.import_module('05_target_matching.watchlist')
models_mod = importlib.import_module('05_target_matching.models')
WatchlistManager = wl_mod.WatchlistManager
WatchlistPriority = models_mod.WatchlistPriority


def main():
    parser = argparse.ArgumentParser(description='Test Watchlist Registry and Shortlisting')
    parser.add_argument('--add', type=str, help='Add registration to watchlist')
    parser.add_argument('--priority', type=str, default='HIGH', choices=['CRITICAL', 'HIGH', 'NORMAL', 'LOW'])
    parser.add_argument('--lookup', type=str, help='Lookup candidate matches for observation')

    args = parser.parse_args()
    wm = WatchlistManager()

    # Pre-populate sample targets
    wm.add_entry('GJ01AB1234', priority=WatchlistPriority.CRITICAL, notes='Wanted vehicle')
    wm.add_entry('MH12DE1432', priority=WatchlistPriority.HIGH, notes='Stolen motorcycle')
    wm.add_entry('DL01AB9999', priority=WatchlistPriority.NORMAL)

    if args.add:
        p = WatchlistPriority[args.priority]
        entry, ok, err = wm.add_entry(args.add, priority=p)
        if ok:
            print(f'Successfully added: {entry.registration} [{entry.normalized_registration}] ID={entry.watchlist_id}')
        else:
            print(f'Failed to add: {err}')

    if args.lookup:
        candidates = wm.lookup_candidates(args.lookup)
        print(f'\nLookup candidates for \"{args.lookup}\": ({len(candidates)} shortlisted)')
        for c in candidates:
            print(f'  • {c.normalized_registration} (Priority: {c.priority.value}) ID={c.watchlist_id}')


if __name__ == '__main__':
    main()
