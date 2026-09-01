import sys
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import time

def init_database_schemas():
    print("=== Initializing SentinelTrack PostgreSQL Schemas ===")
    db_m = importlib.import_module("00_foundation.registry.database")
    
    conn = None
    max_retries = 15
    for attempt in range(1, max_retries + 1):
        try:
            conn = db_m.get_connection()
            print(f"Connected to PostgreSQL on attempt {attempt}/{max_retries}.")
            break
        except Exception as e:
            if attempt < max_retries:
                print(f"Waiting for PostgreSQL to accept connections (attempt {attempt}/{max_retries}): {e}")
                time.sleep(1.0)
            else:
                print(f"Could not connect to PostgreSQL after {max_retries} attempts: {e}")
                return 1

    if conn is None:
        return 1

    schema_files = [
        REPO_ROOT / "00_foundation" / "registry" / "schema.sql",
        REPO_ROOT / "05_target_matching" / "schema.sql",
        REPO_ROOT / "07_route_engine" / "schema.sql",
        REPO_ROOT / "10_security" / "schema.sql"
    ]

    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            for sf in schema_files:
                if sf.exists():
                    print(f"Applying schema file: {sf.name}")
                    sql = sf.read_text(encoding="utf-8")
                    cur.execute(sql)

        conn.close()
        print("Database schemas initialized successfully (no sample cameras inserted).")
        return 0


    except Exception as e:
        print(f"Error applying database schemas: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(init_database_schemas())
