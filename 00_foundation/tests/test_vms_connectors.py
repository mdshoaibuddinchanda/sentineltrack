import json
import importlib
import pytest
from xml.etree import ElementTree as ET

OGCFeaturesConnector = importlib.import_module("00_foundation.vms.ogc_features").OGCFeaturesConnector
ONVIFProfileTConnector = importlib.import_module("00_foundation.vms.onvif").ONVIFProfileTConnector
ConnectorDefinition = importlib.import_module("00_foundation.vms.config").ConnectorDefinition


class FakeResponse:
    def __init__(self, payload, *, is_json=False):
        if is_json:
            self._payload = payload
            self.content = json.dumps(payload).encode("utf-8")
        else:
            self._payload = None
            self.content = payload.encode("utf-8")

    def raise_for_status(self):
        return None

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class FakeOGCSession:
    def __init__(self, payload):
        self.payload = payload
        self.last_headers = None

    def get(self, url, **kwargs):
        self.last_headers = kwargs["headers"]
        return FakeResponse(self.payload, is_json=True)


def test_ogc_features_connector_normalizes_camera_and_preserves_coordinate_quality():
    session = FakeOGCSession({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": "A-17",
            "geometry": {"type": "Point", "coordinates": [72.5714, 23.0225]},
            "properties": {
                "name": "Junction A",
                "department": "Municipal Control Room",
                "location_quality": "VERIFIED",
                "coordinate_source": "Municipal GIS survey 2026",
                "streams": {"rtsp": "rtsp://10.0.0.17/live"},
            },
        }],
    })
    connector = OGCFeaturesConnector(
        connector_id="org-a",
        organization="Organization A",
        source_system="ORG_A_OGC",
        items_url="https://vms-a.example.gov/collections/cameras/items",
        camera_id_prefix="orga",
        bearer_token="not-logged",
        session=session,
    )
    records = connector.discover()
    assert len(records) == 1
    record = records[0]
    assert record.camera_id == "orga:A-17"
    assert record.organization == "Organization A"
    assert record.latitude == 23.0225
    assert record.longitude == 72.5714
    assert record.location_quality == "VERIFIED"
    assert record.coordinate_source == "Municipal GIS survey 2026"
    assert session.last_headers["Authorization"] == "Bearer not-logged"


class FakeONVIFSession:
    def post(self, endpoint, **kwargs):
        action = kwargs["headers"]["Content-Type"]
        if "GetServices" in action:
            xml = """
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                        xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
              <s:Body><tds:GetServicesResponse><tds:Service>
                <tds:Namespace>http://www.onvif.org/ver20/media/wsdl</tds:Namespace>
                <tds:XAddr>http://10.1.2.3/onvif/media2</tds:XAddr>
              </tds:Service></tds:GetServicesResponse></s:Body>
            </s:Envelope>
            """
        elif "GetDeviceInformation" in action:
            xml = """
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                        xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
              <s:Body><tds:GetDeviceInformationResponse>
                <tds:Manufacturer>Vendor B</tds:Manufacturer><tds:Model>T-4K</tds:Model>
                <tds:FirmwareVersion>2.1</tds:FirmwareVersion><tds:SerialNumber>SN-17</tds:SerialNumber>
                <tds:HardwareId>HW-9</tds:HardwareId>
              </tds:GetDeviceInformationResponse></s:Body>
            </s:Envelope>
            """
        elif "GetScopes" in action:
            xml = """
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                        xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
              <s:Body><tds:GetScopesResponse><tds:Scopes>
                <tds:ScopeItem>onvif://www.onvif.org/name/Traffic_Junction_B</tds:ScopeItem>
              </tds:Scopes></tds:GetScopesResponse></s:Body>
            </s:Envelope>
            """
        elif "GetProfiles" in action:
            xml = """
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                        xmlns:tr2="http://www.onvif.org/ver20/media/wsdl"
                        xmlns:tt="http://www.onvif.org/ver10/schema">
              <s:Body><tr2:GetProfilesResponse>
                <tr2:Profiles token="low"><tt:Name>Low</tt:Name><tt:Resolution><tt:Width>640</tt:Width><tt:Height>360</tt:Height></tt:Resolution></tr2:Profiles>
                <tr2:Profiles token="main"><tt:Name>Main</tt:Name><tt:Resolution><tt:Width>3840</tt:Width><tt:Height>2160</tt:Height></tt:Resolution></tr2:Profiles>
              </tr2:GetProfilesResponse></s:Body>
            </s:Envelope>
            """
        elif "GetStreamUri" in action:
            xml = """
            <s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"
                        xmlns:tr2="http://www.onvif.org/ver20/media/wsdl">
              <s:Body><tr2:GetStreamUriResponse><tr2:Uri>rtsp://user:pass@10.1.2.3/main</tr2:Uri></tr2:GetStreamUriResponse></s:Body>
            </s:Envelope>
            """
        else:
            raise AssertionError(action)
        return FakeResponse(xml)


def test_onvif_profile_t_connector_discovers_best_profile_and_strips_url_credentials():
    connector = ONVIFProfileTConnector(
        connector_id="org-b-camera-17",
        organization="Organization B",
        source_system="ORG_B_ONVIF",
        device_service_url="http://10.1.2.3/onvif/device_service",
        camera_external_id="camera-17",
        camera_id_prefix="orgb",
        username="operator",
        password="secret",
        allow_insecure_http=True,
        session=FakeONVIFSession(),
    )
    record = connector.discover()[0]
    assert record.camera_id == "orgb:camera-17"
    assert record.name == "Traffic Junction B"
    assert record.width == 3840
    assert record.height == 2160
    assert record.rtsp_url == "rtsp://10.1.2.3/main"
    assert record.raw_metadata["connector_provenance"]["stream_credentials_stripped"] is True
    assert record.location_quality == "UNKNOWN"


def test_connector_definition_rejects_unproven_coordinates_and_partial_credentials():
    base = {
        "connector_id": "org-b-camera-17",
        "connector_type": "ONVIF_PROFILE_T",
        "organization": "Organization B",
        "source_system": "ORG_B_ONVIF",
        "camera_id_prefix": "orgb",
        "endpoint": "https://vms-b.example.gov.in/onvif/device_service",
        "camera_external_id": "camera-17",
    }
    with pytest.raises(ValueError, match="coordinate_source"):
        ConnectorDefinition.model_validate({**base, "latitude": 23.0, "longitude": 72.5})
    with pytest.raises(ValueError, match="configured together"):
        ConnectorDefinition.model_validate({**base, "username_env": "VMS_B_USER"})


def test_connector_definition_is_https_by_default_and_never_accepts_url_credentials():
    base = {
        "connector_id": "org-a",
        "connector_type": "OGC_API_FEATURES",
        "organization": "Organization A",
        "source_system": "ORG_A_OGC",
        "camera_id_prefix": "orga",
    }
    with pytest.raises(ValueError, match="must be HTTPS"):
        ConnectorDefinition.model_validate({**base, "endpoint": "http://vms-a.example.gov.in/cameras"})
    with pytest.raises(ValueError, match="embedded credentials"):
        ConnectorDefinition.model_validate({**base, "endpoint": "https://user:pass@vms-a.example.gov.in/cameras"})


def test_onvif_service_discovery_cannot_escape_the_approved_host_allowlist():
    connector = ONVIFProfileTConnector(
        connector_id="org-b-camera-17",
        organization="Organization B",
        source_system="ORG_B_ONVIF",
        device_service_url="https://camera.example.gov.in/onvif/device_service",
        camera_external_id="camera-17",
        camera_id_prefix="orgb",
        session=FakeONVIFSession(),
    )
    with pytest.raises(Exception, match="not approved"):
        connector._post(
            "https://untrusted.example/onvif/media",
            "GetProfiles",
            ET.Element("GetProfiles"),
        )
