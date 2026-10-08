"""Standards-based adapters for heterogeneous camera/VMS catalogues."""

from .base import BaseVMSConnector, VMSConnectorError
from .config import ConnectorDefinition, build_connector, load_connector_definitions
from .ogc_features import OGCFeaturesConnector
from .onvif import ONVIFProfileTConnector

__all__ = [
    "BaseVMSConnector",
    "VMSConnectorError",
    "ConnectorDefinition",
    "build_connector",
    "load_connector_definitions",
    "OGCFeaturesConnector",
    "ONVIFProfileTConnector",
]
