"""Authenticated client for the organizer-provided Sentinel camera catalogue.

The current portal publishes the catalogue at ``/cameras.json`` and protects
the HLS media behind a password session. The client also probes the older
``/api/ingest`` route for compatibility. It keeps the authorized session in
memory and can export it in FFmpeg's cookie format without ever putting the
password or cookie in a URL or log message.
"""

from __future__ import annotations

import os
import threading
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv


load_dotenv()


class CatalogueError(RuntimeError):
    """Base error with a stable, operator-facing diagnostic code."""

    code = "CATALOGUE_ERROR"


class CatalogueAuthenticationRequired(CatalogueError):
    code = "AUTH_REQUIRED"


class CatalogueAuthenticationFailed(CatalogueError):
    code = "AUTH_FAILED"


class CatalogueConnectionError(CatalogueError):
    code = "CATALOGUE_UNREACHABLE"


class CatalogueResponseError(CatalogueError):
    code = "CATALOGUE_INVALID_RESPONSE"


def _is_json_response(response: requests.Response) -> bool:
    content_type = response.headers.get("content-type", "").lower()
    return "application/json" in content_type or "text/json" in content_type


def _looks_like_login(response: requests.Response) -> bool:
    final_path = urlparse(response.url).path.rstrip("/").lower()
    if final_path.endswith("/auth/login"):
        return True
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        return False
    sample = response.text[:4096].lower()
    return "restricted feed access" in sample or "name=\"password\"" in sample


class SentinelCatalogueClient:
    """Fetch the camera registry and retain the authorized media session."""

    def __init__(
        self,
        host: str | None = None,
        password: str | None = None,
        timeout_s: float = 15.0,
        session: requests.Session | None = None,
    ):
        configured_host = host or os.getenv("SENTINEL_HOST")
        if not configured_host:
            raise RuntimeError("SENTINEL_HOST is missing from .env")

        self.host = configured_host.rstrip("/")
        self.catalogue_url = f"{self.host}/api/ingest"
        self.password = password if password is not None else os.getenv("SENTINEL_ACCESS_PASSWORD", "")
        self.timeout_s = max(1.0, float(timeout_s))
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", "SentinelTrack/1.0")
        self.effective_host = self.host
        self.authenticated = False
        self._lock = threading.RLock()

    def _get_catalogue(self, url: str | None = None) -> requests.Response:
        request_url = url or self.catalogue_url
        try:
            return self.session.get(
                request_url,
                timeout=self.timeout_s,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise CatalogueConnectionError(
                f"The organizer catalogue could not be reached: {exc}"
            ) from exc

    def _get_authorized_catalogue(self, url: str) -> requests.Response:
        """Fetch a catalogue endpoint, authenticating when the portal asks."""
        response = self._get_catalogue(url)
        if _looks_like_login(response):
            self._authenticate(response)
            response = self._get_catalogue(url)

        if _looks_like_login(response):
            raise CatalogueAuthenticationFailed(
                "The organizer feed session did not authorize the catalogue."
            )

        return response

    def _authenticate(self, login_response: requests.Response) -> None:
        if not self.password:
            raise CatalogueAuthenticationRequired(
                "The organizer feed portal requires SENTINEL_ACCESS_PASSWORD."
            )

        login_url = urljoin(login_response.url, "/auth/login")
        try:
            response = self.session.post(
                login_url,
                data={"password": self.password},
                timeout=self.timeout_s,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise CatalogueConnectionError(
                f"The organizer authentication service could not be reached: {exc}"
            ) from exc

        if response.status_code >= 400 or _looks_like_login(response):
            raise CatalogueAuthenticationFailed(
                "The organizer feed password was rejected or the session was not created."
            )

        self.authenticated = True

    def fetch(self) -> dict | list:
        """Return a validated JSON catalogue, authenticating once if required."""
        with self._lock:
            response = self._get_authorized_catalogue(self.catalogue_url)

            # The organizer's current portal publishes its authenticated
            # registry at /cameras.json. Keep /api/ingest as the primary
            # contract for deployments that expose it, then fall back only
            # when that endpoint is absent.
            if response.status_code == 404 and self.catalogue_url.endswith("/api/ingest"):
                portal_catalogue_url = f"{self.host}/cameras.json"
                response = self._get_authorized_catalogue(portal_catalogue_url)
                if response.status_code < 400:
                    self.catalogue_url = portal_catalogue_url

            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                raise CatalogueConnectionError(
                    f"The organizer catalogue returned HTTP {response.status_code}."
                ) from exc

            if not _is_json_response(response):
                raise CatalogueResponseError(
                    "The organizer catalogue returned HTML or another non-JSON response."
                )

            try:
                payload = response.json()
            except ValueError as exc:
                raise CatalogueResponseError(
                    "The organizer catalogue response was not valid JSON."
                ) from exc

            if not isinstance(payload, (dict, list)):
                raise CatalogueResponseError(
                    "The organizer catalogue JSON must be an object or a list."
                )

            parsed = urlparse(response.url)
            if parsed.scheme and parsed.netloc:
                self.effective_host = f"{parsed.scheme}://{parsed.netloc}"
            self.authenticated = bool(self.session.cookies) or self.authenticated
            return payload

    def get_ffmpeg_cookies(self, _url: str | None = None) -> str:
        """Return cookies in the syntax expected by FFmpeg's HTTP protocol."""
        with self._lock:
            lines: list[str] = []
            for cookie in self.session.cookies:
                path = cookie.path or "/"
                domain = cookie.domain or urlparse(self.effective_host).hostname or ""
                line = f"{cookie.name}={cookie.value}; path={path};"
                if domain:
                    line += f" domain={domain};"
                lines.append(line)
            return ("\n".join(lines) + "\n") if lines else ""

    def diagnostics(self) -> dict[str, object]:
        """Return non-secret state suitable for readiness endpoints."""
        return {
            "catalogue_url": self.catalogue_url,
            "effective_host": self.effective_host,
            "authenticated": self.authenticated,
            "session_cookie_count": len(self.session.cookies),
        }
