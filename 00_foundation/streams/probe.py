import json
import subprocess


def probe_stream(url: str, timeout: int = 15) -> dict:
    command = [
        "ffprobe",
        "-v",
        "error",
    ]

    if url.startswith("rtsp://") or url.startswith("rtsp:"):
        command.extend(["-rtsp_transport", "tcp"])

    command.extend([
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,avg_frame_rate,r_frame_rate",
        "-of",
        "json",
        url,
    ])

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Connection timed out (10s)",
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }

    if result.returncode != 0:
        return {
            "success": False,
            "error": result.stderr.strip(),
        }


    data = json.loads(
        result.stdout
    )

    streams = data.get(
        "streams",
        [],
    )

    if not streams:

        return {
            "success": False,
            "error": "No video stream found",
        }

    stream = streams[0]

    fps_val = None
    fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
    if fps_raw and fps_raw != "0/0":
        try:
            if "/" in str(fps_raw):
                num, den = str(fps_raw).split("/")
                if float(den) != 0:
                    fps_val = round(float(num) / float(den), 2)
            else:
                fps_val = round(float(fps_raw), 2)
        except (ValueError, ZeroDivisionError):
            fps_val = None

    return {
        "success": True,
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "reported_fps": fps_val,
    }


# Backward compatibility alias
probe_rtsp = probe_stream
