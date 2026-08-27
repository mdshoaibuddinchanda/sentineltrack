import sys
import argparse
import importlib

repo_mod = importlib.import_module('05_target_matching.repository')
history_mod = importlib.import_module('05_target_matching.history')
TargetMatchingRepository = repo_mod.TargetMatchingRepository
HistoricalSearchService = history_mod.HistoricalSearchService


def main():
    parser = argparse.ArgumentParser(description='Search Historical Vehicle Sightings')
    parser.add_argument('query', type=str, help='Plate query or wildcard (e.g. GJ01AB* or MH12DE1432)')
    parser.add_argument('--camera', type=str, default=None, help='Filter by camera ID')
    parser.add_argument('--min_score', type=float, default=0.50, help='Minimum match score')

    args = parser.parse_args()
    repo = TargetMatchingRepository()
    svc = HistoricalSearchService(repository=repo)

    results = svc.search_vehicle_history(
        query=args.query,
        camera_id=args.camera,
        min_match_score=args.min_score
    )

    print(f'Found {len(results)} sighting(s) matching query \"{args.query}\":')
    for r in results:
        print(f"  • {r['registration_candidate']} (Cam: {r['camera_id']}, Score: {r['match_score']:.2f}, Time: {r['created_at']})")


if __name__ == '__main__':
    main()
