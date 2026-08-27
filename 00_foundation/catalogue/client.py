import os
import requests

from dotenv import load_dotenv


load_dotenv()


class SentinelCatalogueClient:

    def __init__(self):
        host = os.getenv("SENTINEL_HOST")

        if not host:
            raise RuntimeError(
                "SENTINEL_HOST is missing from .env"
            )

        self.host = host.rstrip("/")

        self.catalogue_url = (
            f"{self.host}/api/ingest"
        )

    def fetch(self) -> dict | list:

        response = requests.get(
            self.catalogue_url,
            timeout=15,
        )

        response.raise_for_status()

        return response.json()