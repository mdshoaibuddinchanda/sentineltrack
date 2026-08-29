import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.preflight import main


def run_preflight() -> int:
    """Backward-compatible entry point for the former P11 command."""
    return main([])

if __name__ == "__main__":
    sys.exit(main())
