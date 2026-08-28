import sys
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def init_database_schemas():
    print("=== Initializing SentinelTrack PostgreSQL Schemas ===")
    try:
        db_m = importlib.import_module("00_foundation.registry.database")
        conn = db_m.get_connection()
    except Exception as e:
        print(f"Skipping database schema initialization (database unavailable): {e}")
        return 0

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
                    print(f"Applying schema: {sf.name}")
                    sql = sf.read_text(encoding="utf-8")
                    cur.execute(sql)
        conn.close()
        print("Database schemas initialized successfully.")
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
