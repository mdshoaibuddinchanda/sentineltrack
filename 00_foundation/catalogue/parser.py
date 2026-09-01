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
