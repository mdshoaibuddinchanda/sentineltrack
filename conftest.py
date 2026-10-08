"""Repository-wide pytest safeguards for a developer's local PostgreSQL data."""

from __future__ import annotations

import importlib
import os
import warnings

import pytest


_OPERATIONAL_KEYS = {
    "cameras": "camera_id",
    "camera_health_events": "id",
    "watchlist_entries": "watchlist_id",
    "vehicle_sightings": "sighting_id",
    "target_matches": "match_id",
    "alerts": "alert_id",
    "route_analysis_runs": "route_id",
    "route_segments": "segment_id",
}


def _snapshot(cur) -> dict[str, set[object]]:
    state: dict[str, set[object]] = {}
    for table, key in _OPERATIONAL_KEYS.items():
        cur.execute(f"SELECT {key} FROM {table}")
        state[table] = {row[0] for row in cur.fetchall()}
    return state


def _delete_rows_added_by_tests(cur, table: str, key: str, baseline: set[object]) -> None:
    if not baseline:
        cur.execute(f"DELETE FROM {table}")
        return
    cur.execute(f"DELETE FROM {table} WHERE NOT ({key} = ANY(%s))", (list(baseline),))


@pytest.fixture(scope="session", autouse=True)
def preserve_local_operational_database():
    """Remove only rows added by this test session, preserving pre-existing data.

    The suite intentionally exercises production PostgreSQL repositories. A
    snapshot/finalizer prevents those fixtures from becoming dashboard data on
    a developer workstation while remaining harmless on an ephemeral CI DB.
    """
    if os.getenv("SENTINEL_TEST_DB_CLEANUP", "true").lower() not in {"true", "1", "yes"}:
        yield
        return

    try:
        database = importlib.import_module("00_foundation.registry.database")
        with database.get_connection() as conn:
            with conn.cursor() as cur:
                baseline = _snapshot(cur)
    except Exception:
        # Unit-only environments are allowed to run without PostgreSQL.
        yield
        return

    yield

    try:
        with database.get_connection() as conn:
            with conn.cursor() as cur:
                # Foreign-key dependants first.
                for table in (
                    "route_segments",
                    "alerts",
                    "target_matches",
                    "route_analysis_runs",
                    "vehicle_sightings",
                    "watchlist_entries",
                    "camera_health_events",
                    "cameras",
                ):
                    _delete_rows_added_by_tests(
                        cur,
                        table,
                        _OPERATIONAL_KEYS[table],
                        baseline[table],
                    )
    except Exception as exc:
        warnings.warn(f"Could not restore the local operational database after pytest: {exc}")
