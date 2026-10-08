import json
import subprocess
import time

import cv2


def _probe_with_opencv(url: str, timeout: int = 15) -> dict:
    """Probe one real frame when the optional ffprobe binary is unavailable."""
    timeout_ms = max(1000, int(timeout * 1000))
    capture = None
    started = time.monotonic()
    try:
        params = [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            timeout_ms,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            timeout_ms,
        ]
        try:
            capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
        except (TypeError, cv2.error):
            capture = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

        if capture is None or not capture.isOpened():
            return {
                "success": False,
                "error": "OpenCV could not open the source",
            }

        ok, frame = capture.read()
        if not ok or frame is None:
            return {
                "success": False,
                "error": "OpenCV opened the source but decoded no frame",
            }

        height, width = frame.shape[:2]
        fps = capture.get(cv2.CAP_PROP_FPS)
        reported_fps = round(float(fps), 2) if fps and fps > 0 else None

        return {
            "success": True,
            "codec": None,
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or width),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or height),
            "reported_fps": reported_fps,
            "probe_backend": "opencv",
            "first_frame_latency_ms": round((time.monotonic() - started) * 1000.0, 2),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"OpenCV probe failed: {exc}",
        }
    finally:
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass


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

    except FileNotFoundError:
        return _probe_with_opencv(url, timeout=timeout)
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

