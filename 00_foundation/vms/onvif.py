from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

import requests
from requests.auth import HTTPDigestAuth

from ..catalogue.models import CameraRecord
from .base import BaseVMSConnector, VMSConnectorError, normalized_camera_id, validate_connector_url


SOAP = "http://www.w3.org/2003/05/soap-envelope"
DEVICE = "http://www.onvif.org/ver10/device/wsdl"
MEDIA1 = "http://www.onvif.org/ver10/media/wsdl"
MEDIA2 = "http://www.onvif.org/ver20/media/wsdl"
SCHEMA = "http://www.onvif.org/ver10/schema"
WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
PASSWORD_DIGEST = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-username-token-profile-1.0#PasswordDigest"
)
BASE64_BINARY = (
    "http://docs.oasis-open.org/wss/2004/01/"
    "oasis-200401-wss-soap-message-security-1.0#Base64Binary"
)
MAX_XML_BYTES = 5 * 1024 * 1024


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(root: ET.Element, name: str) -> Optional[str]:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _scope_value(scopes: list[str], category: str) -> Optional[str]:
    marker = f"onvif://www.onvif.org/{category}/"
    for scope in scopes:
        if scope.startswith(marker):
            return unquote(scope[len(marker):]).replace("_", " ")
    return None


def _strip_url_credentials(url: str) -> tuple[str, bool]:
    parsed = urlsplit(url)
    had_credentials = parsed.username is not None or parsed.password is not None
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)), had_credentials


class ONVIFProfileTConnector(BaseVMSConnector):
    """Discover one ONVIF Profile T camera and its preferred RTSP media profile."""

    connector_type = "ONVIF_PROFILE_T"

    def __init__(
        self,
        *,
        connector_id: str,
        organization: str,
        source_system: str,
        device_service_url: str,
        camera_external_id: str,
        camera_id_prefix: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout_s: float = 10.0,
        allow_insecure_http: bool = False,
        session: Optional[requests.Session] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_quality: str = "UNKNOWN",
        coordinate_source: Optional[str] = None,
        allowed_service_hosts: Optional[list[str]] = None,
    ):
        super().__init__(
            connector_id=connector_id,
            organization=organization,
            source_system=source_system,
        )
        self.device_service_url = validate_connector_url(
            device_service_url,
            allow_http=allow_insecure_http,
            label="ONVIF device_service_url",
        )
        self.camera_external_id = camera_external_id
        self.camera_id_prefix = camera_id_prefix
        self.username = username
        self.password = password
        self.timeout_s = max(1.0, min(float(timeout_s), 60.0))
        self.session = session or requests.Session()
        self.latitude = latitude
        self.longitude = longitude
        self.location_quality = location_quality if location_quality in {"VERIFIED", "APPROXIMATE", "UNKNOWN"} else "UNKNOWN"
        self.coordinate_source = coordinate_source
        device_host = (urlsplit(self.device_service_url).hostname or "").lower()
        self.allowed_service_hosts = {
            host.strip().lower()
            for host in ([device_host] + list(allowed_service_hosts or []))
            if host and host.strip()
        }

    def _envelope(self, operation: ET.Element) -> bytes:
        envelope = ET.Element(f"{{{SOAP}}}Envelope")
        if self.username and self.password:
            header = ET.SubElement(envelope, f"{{{SOAP}}}Header")
            security = ET.SubElement(header, f"{{{WSSE}}}Security")
            token = ET.SubElement(security, f"{{{WSSE}}}UsernameToken")
            ET.SubElement(token, f"{{{WSSE}}}Username").text = self.username
            nonce = os.urandom(16)
            created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            digest = base64.b64encode(
                hashlib.sha1(nonce + created.encode("utf-8") + self.password.encode("utf-8")).digest()
            ).decode("ascii")
            password = ET.SubElement(token, f"{{{WSSE}}}Password", {"Type": PASSWORD_DIGEST})
            password.text = digest
            nonce_el = ET.SubElement(token, f"{{{WSSE}}}Nonce", {"EncodingType": BASE64_BINARY})
            nonce_el.text = base64.b64encode(nonce).decode("ascii")
            ET.SubElement(token, f"{{{WSU}}}Created").text = created
        body = ET.SubElement(envelope, f"{{{SOAP}}}Body")
        body.append(operation)
        return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)

    def _post(self, endpoint: str, action: str, operation: ET.Element) -> ET.Element:
        endpoint = validate_connector_url(
            endpoint,
            allow_http=urlsplit(self.device_service_url).scheme.lower() == "http",
            label="ONVIF service endpoint",
        )
        endpoint_host = (urlsplit(endpoint).hostname or "").lower()
        if endpoint_host not in self.allowed_service_hosts:
            raise VMSConnectorError(
                "ONVIF service discovery returned a host that is not approved by connector configuration.",
                "UNAPPROVED_SERVICE_HOST",
            )
        headers = {
            "Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"',
            "User-Agent": "SentinelTrack/1.0 ONVIF-Profile-T-Connector",
        }
        auth = HTTPDigestAuth(self.username, self.password) if self.username and self.password else None
        try:
            response = self.session.post(
                endpoint,
                data=self._envelope(operation),
                headers=headers,
                auth=auth,
                timeout=self.timeout_s,
                allow_redirects=False,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise VMSConnectorError(
                f"ONVIF request failed for {action.rsplit('/', 1)[-1]}: {type(exc).__name__}.",
                "ONVIF_REQUEST_FAILED",
            ) from exc
        if len(response.content) > MAX_XML_BYTES:
            raise VMSConnectorError("ONVIF response exceeds the 5 MiB safety limit.", "RESPONSE_TOO_LARGE")
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise VMSConnectorError("ONVIF device returned invalid SOAP XML.", "INVALID_SOAP_XML") from exc
        for element in root.iter():
            if _local_name(element.tag) == "Fault":
                reason = _first_text(element, "Text") or "ONVIF device returned a SOAP fault."
                raise VMSConnectorError(reason[:300], "ONVIF_SOAP_FAULT")
        return root

    def _get_services(self) -> tuple[dict[str, str], ET.Element]:
        operation = ET.Element(f"{{{DEVICE}}}GetServices")
        ET.SubElement(operation, f"{{{DEVICE}}}IncludeCapability").text = "false"
        root = self._post(
            self.device_service_url,
            f"{DEVICE}/GetServices",
            operation,
        )
        services: dict[str, str] = {}
        for service in root.iter():
            if _local_name(service.tag) != "Service":
                continue
            namespace = _first_text(service, "Namespace")
            xaddr = _first_text(service, "XAddr")
            if namespace and xaddr:
                services[namespace] = xaddr
        return services, root

    def _get_device_information(self) -> ET.Element:
        operation = ET.Element(f"{{{DEVICE}}}GetDeviceInformation")
        return self._post(
            self.device_service_url,
            f"{DEVICE}/GetDeviceInformation",
            operation,
        )

    def _get_scopes(self) -> list[str]:
        operation = ET.Element(f"{{{DEVICE}}}GetScopes")
        root = self._post(self.device_service_url, f"{DEVICE}/GetScopes", operation)
        return [
            element.text.strip()
            for element in root.iter()
            if _local_name(element.tag) == "ScopeItem" and element.text and element.text.strip()
        ]

    def _get_profiles(self, media_endpoint: str, namespace: str) -> tuple[ET.Element, list[tuple[str, str, int, int]]]:
        operation = ET.Element(f"{{{namespace}}}GetProfiles")
        root = self._post(media_endpoint, f"{namespace}/GetProfiles", operation)
        profiles: list[tuple[str, str, int, int]] = []
        for element in root.iter():
            if _local_name(element.tag) not in {"Profiles", "Profile"}:
                continue
            token = element.attrib.get("token") or element.attrib.get("Token")
            if not token:
                continue
            name = _first_text(element, "Name") or token
            width_text = _first_text(element, "Width") or "0"
            height_text = _first_text(element, "Height") or "0"
            try:
                width, height = int(width_text), int(height_text)
            except ValueError:
                width = height = 0
            profiles.append((token, name, width, height))
        if not profiles:
            raise VMSConnectorError("ONVIF media service returned no usable profiles.", "NO_MEDIA_PROFILES")
        return root, profiles

    def _get_stream_uri(self, media_endpoint: str, namespace: str, profile_token: str) -> str:
        operation = ET.Element(f"{{{namespace}}}GetStreamUri")
        if namespace == MEDIA2:
            ET.SubElement(operation, f"{{{namespace}}}Protocol").text = "RTSP"
            ET.SubElement(operation, f"{{{namespace}}}ProfileToken").text = profile_token
        else:
            setup = ET.SubElement(operation, f"{{{namespace}}}StreamSetup")
            ET.SubElement(setup, f"{{{SCHEMA}}}Stream").text = "RTP-Unicast"
            transport = ET.SubElement(setup, f"{{{SCHEMA}}}Transport")
            ET.SubElement(transport, f"{{{SCHEMA}}}Protocol").text = "RTSP"
            ET.SubElement(operation, f"{{{namespace}}}ProfileToken").text = profile_token
        root = self._post(media_endpoint, f"{namespace}/GetStreamUri", operation)
        uri = _first_text(root, "Uri")
        if not uri:
            raise VMSConnectorError("ONVIF media profile returned no RTSP URI.", "NO_STREAM_URI")
        parsed = urlsplit(uri)
        if parsed.scheme.lower() not in {"rtsp", "rtsps"} or not parsed.hostname:
            raise VMSConnectorError("ONVIF media profile returned an invalid RTSP URI.", "INVALID_STREAM_URL")
        return uri

    def discover(self) -> list[CameraRecord]:
        services, _ = self._get_services()
        device_info = self._get_device_information()
        scopes = self._get_scopes()
        if MEDIA2 in services:
            media_namespace, media_endpoint = MEDIA2, services[MEDIA2]
        elif MEDIA1 in services:
            media_namespace, media_endpoint = MEDIA1, services[MEDIA1]
        else:
            raise VMSConnectorError("ONVIF device exposes no Media or Media2 service.", "NO_MEDIA_SERVICE")

        _, profiles = self._get_profiles(media_endpoint, media_namespace)
        profile_token, profile_name, width, height = max(
            profiles,
            key=lambda profile: (profile[2] * profile[3], profile[2], profile[3]),
        )
        stream_uri, credentials_stripped = _strip_url_credentials(
            self._get_stream_uri(media_endpoint, media_namespace, profile_token)
        )
        serial = _first_text(device_info, "SerialNumber")
        name = _scope_value(scopes, "name") or profile_name or self.camera_external_id
        location_label = _scope_value(scopes, "location")
        coordinate_source = self.coordinate_source
        if self.latitude is not None and not coordinate_source:
            coordinate_source = f"VMS_CONFIG:{self.connector_id}"

        return [
            CameraRecord(
                camera_id=normalized_camera_id(self.camera_id_prefix, self.camera_external_id),
                external_id=self.camera_external_id,
                name=name,
                organization=self.organization,
                source_system=self.source_system,
                onboarding_method="ONVIF_PROFILE_T_SYNC",
                latitude=self.latitude,
                longitude=self.longitude,
                location_quality=self.location_quality if self.latitude is not None else "UNKNOWN",
                coordinate_source=coordinate_source,
                codec=None,
                width=width or None,
                height=height or None,
                live=True,
                rtsp_url=stream_uri,
                raw_metadata={
                    "connector_provenance": {
                        "connector_id": self.connector_id,
                        "connector_type": self.connector_type,
                        "profile_namespace": media_namespace,
                        "profile_token": profile_token,
                        "stream_credentials_stripped": credentials_stripped,
                    },
                    "device": {
                        "manufacturer": _first_text(device_info, "Manufacturer"),
                        "model": _first_text(device_info, "Model"),
                        "firmware_version": _first_text(device_info, "FirmwareVersion"),
                        "serial_number": serial,
                        "hardware_id": _first_text(device_info, "HardwareId"),
                        "location_label": location_label,
                    },
                },
            )
        ]
