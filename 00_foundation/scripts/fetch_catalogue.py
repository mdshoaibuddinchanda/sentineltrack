import json
from pathlib import Path
from datetime import datetime, timezone

try:
    from ..catalogue.client import SentinelCatalogueClient
    from ..catalogue.parser import parse_catalogue
    from ..registry.database import upsert_camera
except (ImportError, ValueError):
    from catalogue.client import SentinelCatalogueClient
    from catalogue.parser import parse_catalogue
    from registry.database import upsert_camera



OUTPUT_DIR = Path("data/catalogue")


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    client = SentinelCatalogueClient()

    # 1. Download /api/ingest
    payload = client.fetch()

    # 2. Save original JSON
    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S")

    raw_path = (
        OUTPUT_DIR
        / f"catalogue_{timestamp}.json"
    )

    with raw_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            payload,
            f,
            indent=2,
        )

    # 3. Convert JSON into CameraRecord objects
    cameras = parse_catalogue(payload, base_host=client.effective_host)

    print(
        f"Discovered {len(cameras)} cameras"
    )

    # 4. Save every camera into PostgreSQL
    for camera in cameras:

        upsert_camera(camera)

        print(
            f"[REGISTERED] {camera.camera_id}"
        )

    print(
        f"Raw catalogue saved: {raw_path}"
    )


if __name__ == "__main__":
    main()
