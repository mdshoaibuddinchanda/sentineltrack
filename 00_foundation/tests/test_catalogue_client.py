import importlib

import pytest
import requests


client_m = importlib.import_module("00_foundation.catalogue.client")


class FakeResponse:
    def __init__(self, *, url, content_type="text/html", text="", payload=None, status=200):
        self.url = url
        self.headers = {"content-type": content_type}
        self.text = text
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, get_responses, post_response=None):
        self.headers = {}
        self.cookies = requests.cookies.RequestsCookieJar()
        self._gets = iter(get_responses)
        self._post_response = post_response
        self.post_data = None
        self.get_urls = []

    def get(self, url, **_kwargs):
        self.get_urls.append(url)
        return next(self._gets)

    def post(self, _url, data, **_kwargs):
        self.post_data = data
        self.cookies.set("feed_session", "opaque-token", domain="cctv.corp8.cloud", path="/")
        return self._post_response


def test_catalogue_reports_missing_organizer_password():
    login = FakeResponse(
        url="https://cctv.corp8.cloud/auth/login",
        text='<form><input name="password"></form>Restricted Feed Access',
    )
    client = client_m.SentinelCatalogueClient(
        host="https://live.sentinelgujarat.in",
        password="",
        session=FakeSession([login]),
    )

    with pytest.raises(client_m.CatalogueAuthenticationRequired):
        client.fetch()


def test_catalogue_authenticates_and_exports_ffmpeg_cookie_without_password():
    login = FakeResponse(
        url="https://cctv.corp8.cloud/auth/login",
        text='<form><input name="password"></form>Restricted Feed Access',
    )
    auth_ok = FakeResponse(url="https://cctv.corp8.cloud/")
    catalogue = FakeResponse(
        url="https://cctv.corp8.cloud/api/ingest",
        content_type="application/json",
        payload={"cameras": [{"id": "1"}]},
    )
    session = FakeSession([login, catalogue], post_response=auth_ok)
    client = client_m.SentinelCatalogueClient(
        host="https://live.sentinelgujarat.in",
        password="organizer-secret",
        session=session,
    )

    assert client.fetch() == {"cameras": [{"id": "1"}]}
    assert session.post_data == {"password": "organizer-secret"}
    cookie = client.get_ffmpeg_cookies()
    assert "feed_session=opaque-token" in cookie
    assert "organizer-secret" not in cookie
    assert client.effective_host == "https://cctv.corp8.cloud"


def test_catalogue_falls_back_to_current_authenticated_portal_registry():
    login = FakeResponse(
        url="https://cctv.corp8.cloud/auth/login",
        text='<form><input name="password"></form>Restricted Feed Access',
    )
    auth_ok = FakeResponse(url="https://cctv.corp8.cloud/")
    missing_legacy_endpoint = FakeResponse(
        url="https://cctv.corp8.cloud/api/ingest",
        status=404,
    )
    portal_catalogue = FakeResponse(
        url="https://cctv.corp8.cloud/cameras.json",
        content_type="application/json",
        payload=[{"id": "cam01", "name": "01 Chiman bhai Bridge"}],
    )
    session = FakeSession(
        [login, missing_legacy_endpoint, portal_catalogue],
        post_response=auth_ok,
    )
    client = client_m.SentinelCatalogueClient(
        host="https://cctv.corp8.cloud",
        password="organizer-secret",
        session=session,
    )

    assert client.fetch() == [{"id": "cam01", "name": "01 Chiman bhai Bridge"}]
    assert session.get_urls == [
        "https://cctv.corp8.cloud/api/ingest",
        "https://cctv.corp8.cloud/api/ingest",
        "https://cctv.corp8.cloud/cameras.json",
    ]
    assert client.catalogue_url == "https://cctv.corp8.cloud/cameras.json"
