try:
    from .models import CameraRecord
except (ImportError, ValueError):
    from catalogue.models import CameraRecord



def first_value(data, *keys):

    for key in keys:
        value = data.get(key)

        if value is not None:
            return value

    return None


def parse_camera(item: dict, base_host: str | None = None) -> CameraRecord:

    stream_data = (
        item.get("stream")
        or item.get("streams")
        or {}
    )

    location_data = (
        item.get("location")
        if isinstance(item.get("location"), dict)
        else {}
    )

    camera_id = first_value(
        item,
        "id",
        "camera_id",
        "cameraId",
    )

    if camera_id is None:
        raise ValueError(
            f"Camera has no id: {item}"
        )

    rtsp = first_value(
        item,
        "rtsp",
        "rtsp_url",
        "rtspUrl",
    )

    if rtsp is None and isinstance(stream_data, dict):
        rtsp = first_value(
            stream_data,
            "rtsp",
            "rtsp_url",
        )

    webrtc = first_value(
        item,
        "webrtc",
        "webrtc_url",
        "whep",
    )

    if webrtc is None and isinstance(stream_data, dict):
        webrtc = first_value(
            stream_data,
            "webrtc",
            "whep",
        )

    hls = first_value(
        item,
        "hls",
        "hls_url",
        "hls_live_url",
    )

    if hls is None and isinstance(stream_data, dict):
        hls = first_value(
            stream_data,
            "hls",
            "hls_url",
            "hls_live_url",
        )

    import os
    # The current organizer portal exposes a compact registry containing only
    # {id, name}; its media endpoints follow stable paths. Derive those URLs
    # only for named portal records so generic catalogues do not silently
    # acquire stream endpoints they did not publish.
    if (
        base_host
        and isinstance(item.get("name"), str)
        and item.get("name").strip()
    ):
        portal_id = str(camera_id).lstrip("/")
        if hls is None:
            hls = f"{base_host.rstrip('/')}/{portal_id}/index.m3u8"
        if rtsp is None:
            rtsp_host = os.getenv("SENTINEL_RTSP_HOST", "103.250.160.189").strip()
            rtsp_port = os.getenv("SENTINEL_RTSP_PORT", "8554").strip()
            if rtsp_host:
                rtsp = f"rtsp://{rtsp_host}:{rtsp_port}/stream/{portal_id}"
        if webrtc is None:
            whep_host = os.getenv("SENTINEL_WHEP_HOST", "103.250.160.189").strip()
            whep_port = os.getenv("SENTINEL_WHEP_PORT", "8889").strip()
            if whep_host:
                webrtc = f"http://{whep_host}:{whep_port}/stream/{portal_id}/whep"

    if hls and isinstance(hls, str) and hls.startswith("/"):
        resolved_host = (base_host or os.getenv("SENTINEL_HOST", "")).rstrip("/")
        if resolved_host:
            hls = f"{resolved_host}{hls}"


    latitude = first_value(
        item,
        "latitude",
        "lat",
    )

    longitude = first_value(
        item,
        "longitude",
        "lon",
        "lng",
    )

    if latitude is None:
        latitude = first_value(
            location_data,
            "latitude",
            "lat",
        )

    if longitude is None:
        longitude = first_value(
            location_data,
            "longitude",
            "lon",
            "lng",
        )

    return CameraRecord(

        camera_id=str(camera_id),

        # The organizer payload has a generic name and a useful string
        # location. Prefer the location label while retaining raw_metadata.
        name=(
            item.get("location")
            if isinstance(item.get("location"), str) and item.get("location").strip()
            else first_value(item, "name", "camera_name", "label", "title")
        ),

        department=first_value(
            item,
            "department",
            "owner",
            "agency",
        ),

        latitude=latitude,
        longitude=longitude,

        codec=first_value(
            item,
            "codec",
            "video_codec",
        ),

        width=first_value(
            item,
            "width",
        ),

        height=first_value(
            item,
            "height",
        ),

        reported_fps=first_value(
            item,
            "fps",
            "frame_rate",
        ),

        bitrate=first_value(
            item,
            "bitrate",
        ),

        live=first_value(
            item,
            "live",
            "online",
            "is_active",
            "active",
        ),


        rtsp_url=rtsp,
        webrtc_url=webrtc,
        hls_url=hls,

        raw_metadata=item,
    )


def parse_catalogue(payload, base_host: str | None = None):

    if isinstance(payload, list):
        items = payload

    elif isinstance(payload, dict):

        items = (
            payload.get("cameras")
            or payload.get("streams")
            or payload.get("data")
            or []
        )

    else:
        raise TypeError(
            "Unsupported Sentinel catalogue format"
        )

    return [
        parse_camera(item, base_host=base_host)
        for item in items
    ]
