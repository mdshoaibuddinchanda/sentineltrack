import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import importlib
try:
    probe_mod = importlib.import_module('00_foundation.streams.probe')
    probe_rtsp = probe_mod.probe_rtsp
except Exception:
    from .probe import probe_rtsp


def resolve_stream(
    camera: dict,
    prefer_rtsp: bool = True,
    probe_timeout: float = 3.0,
) -> Tuple[Optional[str], str]:
    """
    Unified stream URL resolver with automatic RTSP/TCP -> HLS/HTTPS fallback.
    Returns: (stream_url, transport_name)
    """
    rtsp_url = camera.get('rtsp_url')
    hls_url = camera.get('hls_url')

    # 1. Prefer RTSP if enabled and URL is present
    if prefer_rtsp and rtsp_url:
        probe_res = probe_rtsp(rtsp_url, timeout=probe_timeout)
        if probe_res.get('success'):
            return rtsp_url, 'RTSP/TCP'

    # 2. Fallback to HLS
    if hls_url:
        return hls_url, 'HLS/HTTPS'

    # 3. Last resort if RTSP was provided without HLS
    if rtsp_url:
        return rtsp_url, 'RTSP/TCP'

    return None, 'NONE'
