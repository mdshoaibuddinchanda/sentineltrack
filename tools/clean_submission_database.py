"""Clean local development records before a real SentinelTrack submission run.

This deliberately preserves the camera catalogue rows whose IDs are numeric,
because those are the currently configured Sentinel catalogue sources. It
removes the non-numeric test/benchmark camera rows and all operational history
generated while exercising the repository locally. Security users and the
append-only security audit trail are preserved.

The command is dry-run by default. Apply it only with both --apply and --yes.
"""

from __future__ import annotations

import argparse
import os

import psycopg
from dotenv import load_dotenv


def connect() -> psycopg.Connection:
    load_dotenv()
    return psycopg.connect(
        host=os.getenv("DATABASE_HOST", "localhost"),
        port=int(os.getenv("DATABASE_PORT", "5432")),
        dbname=os.getenv("DATABASE_NAME", "sentinel"),
        user=os.getenv("DATABASE_USER", "sentinel"),
        password=os.getenv("DATABASE_PASSWORD", "sentinel_password"),
    )


def count_rows(cur, table: str) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cur.fetchone()[0])


def print_inventory(cur) -> None:
    print("Current local database inventory:")
    for table in (
        "cameras",
        "watchlist_entries",
        "vehicle_sightings",
        "target_matches",
        "alerts",
        "route_analysis_runs",
        "route_segments",
        "camera_health_events",
    ):
        print(f"  {table}: {count_rows(cur, table)}")
    cur.execute(
        "SELECT camera_id FROM cameras "
        "WHERE camera_id !~ '^[0-9]+$' ORDER BY camera_id"
    )
    ids = [row[0] for row in cur.fetchall()]
    print(f"  non-numeric camera rows to remove: {len(ids)}")
    if ids:
        print("  " + ", ".join(ids))


def clean_database(clear_watchlist: bool) -> None:
    with connect() as conn:
        with conn.cursor() as cur:
            print_inventory(cur)
            print("\nApplying local submission cleanup...")

            # These tables contain generated observations and derived records.
            # They do not contain model weights or source datasets.
            cur.execute(
                "TRUNCATE TABLE route_segments, route_analysis_runs, alerts, "
                "target_matches, vehicle_sightings RESTART IDENTITY"
            )
            cur.execute("TRUNCATE TABLE camera_health_events RESTART IDENTITY")

            # Camera health events have a foreign key to cameras. Remove the
            # non-numeric development/test registry rows after their events.
            cur.execute("DELETE FROM cameras WHERE camera_id !~ '^[0-9]+$'")

            # Clear stale probe state but retain the verified catalogue source
            # metadata for numeric cameras.
            cur.execute(
                "UPDATE cameras SET stream_status = 'UNKNOWN', "
                "measured_fps = NULL, first_frame_latency_ms = NULL, "
                "last_pts_ms = NULL, last_checked = NULL "
                "WHERE camera_id ~ '^[0-9]+$'"
            )

            if clear_watchlist:
                # The local audit identified the current watchlist as test
                # batches. Real operators can add their authorized targets
                # again through the protected Watchlist page.
                cur.execute("TRUNCATE TABLE watchlist_entries CASCADE")

        conn.commit()

        with conn.cursor() as cur:
            print("Cleaned database inventory:")
            for table in (
                "cameras",
                "watchlist_entries",
                "vehicle_sightings",
                "target_matches",
                "alerts",
                "route_analysis_runs",
                "route_segments",
                "camera_health_events",
            ):
                print(f"  {table}: {count_rows(cur, table)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="perform the cleanup")
    parser.add_argument("--yes", action="store_true", help="confirm the destructive local cleanup")
    parser.add_argument(
        "--clear-watchlist",
        action="store_true",
        help="also remove all current local watchlist entries",
    )
    args = parser.parse_args()

    with connect() as conn:
        with conn.cursor() as cur:
            print_inventory(cur)

    if not args.apply:
        print("\nDry run only. Re-run with --apply --yes to clean these records.")
        return 0
    if not args.yes:
        print("Refusing to modify the database without --yes.")
        return 2

    clean_database(clear_watchlist=args.clear_watchlist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
