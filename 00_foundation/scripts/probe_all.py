import csv
import time
from pathlib import Path

try:
    from ..registry.database import (
        get_all_cameras,
        update_camera_probe_status,
        record_health_event,
    )
    from ..streams.probe import probe_rtsp
except (ImportError, ValueError):
    from registry.database import (
        get_all_cameras,
        update_camera_probe_status,
        record_health_event,
    )
    from streams.probe import probe_rtsp

REPORT_DIR = Path("reports")


def probe_all_cameras():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORT_DIR / "priority0_camera_report.csv"

    cameras = get_all_cameras()
    if not cameras:
        print("[INFO] No cameras found in the registry. Run fetch_catalogue.py first.")
        return

    print(f"[INFO] Probing {len(cameras)} cameras from registry...\n")
    print(f"{'Camera ID':<10} | {'Live':<5} | {'Conn':<7} | {'Transport':<9} | {'Codec':<7} | {'Resolution':<10} | {'PTS':<4} | {'Details'}")
    print("-" * 90)

    report_rows = []
    online_count = 0
    offline_count = 0

    for cam in cameras:
        camera_id = cam["camera_id"]
        is_live = "Yes" if cam.get("live") else "No"
        rtsp_url = cam.get("rtsp_url")
        hls_url = cam.get("hls_url")

        target_url = rtsp_url
        transport = "RTSP/TCP"

        start_time = time.time()
        result = {"success": False, "error": "No stream URL"}

        # 1. Try RTSP
        if rtsp_url:
            result = probe_rtsp(rtsp_url, timeout=5)

        # 2. If RTSP failed and HLS is available, fallback to HLS
        if not result.get("success") and hls_url:
            hls_result = probe_rtsp(hls_url, timeout=10)
            if hls_result.get("success"):
                result = hls_result
                target_url = hls_url
                transport = "HLS/HTTPS"

        latency_ms = (time.time() - start_time) * 1000.0

        if result.get("success"):
            codec = (result.get("codec") or "h264").upper()
            width = result.get("width") or 0
            height = result.get("height") or 0
            fps = result.get("reported_fps") or 0.0
            res_str = f"{width}x{height}" if width and height else "—"

            update_camera_probe_status(
                camera_id=camera_id,
                stream_status="ONLINE",
                codec=codec,
                width=width if width else None,
                height=height if height else None,
                measured_fps=float(fps) if fps else None,
                first_frame_latency_ms=round(latency_ms, 2),
            )
            record_health_event(
                camera_id=camera_id,
                event_type="PROBE_SUCCESS",
                message=f"Probe OK ({transport}): {codec} {res_str} @ {fps}fps (latency: {latency_ms:.1f}ms)",
            )
            print(f"{camera_id:<10} | {is_live:<5} | {'OK':<7} | {transport:<9} | {codec:<7} | {res_str:<10} | {'OK':<4} | {latency_ms:.0f}ms")
            report_rows.append({
                "Camera": camera_id,
                "Live": is_live,
                "Connection": "OK",
                "Transport": transport,
                "Codec": codec,
                "Resolution": res_str,
                "PTS": "OK",
                "Error": "",
            })
            online_count += 1
        else:
            err = result.get("error", "No stream URL found")
            err_short = err.splitlines()[-1] if err else "Probe failed"
            update_camera_probe_status(
                camera_id=camera_id,
                stream_status="OFFLINE",
                first_frame_latency_ms=round(latency_ms, 2),
            )
            record_health_event(
                camera_id=camera_id,
                event_type="PROBE_FAILED",
                message=f"Probe failed: {err_short}",
            )
            print(f"{camera_id:<10} | {is_live:<5} | {'FAILED':<7} | {transport:<9} | {'—':<7} | {'—':<10} | {'—':<4} | {err_short[:30]}")
            report_rows.append({
                "Camera": camera_id,
                "Live": is_live,
                "Connection": "FAILED",
                "Transport": transport,
                "Codec": "—",
                "Resolution": "—",
                "PTS": "—",
                "Error": err_short,
            })
            offline_count += 1

    print("-" * 90)
    print(f"[SUMMARY] Total: {len(cameras)} | Online: {online_count} | Offline/Unreachable: {offline_count}")

    # Write CSV report
    with report_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Camera", "Live", "Connection", "Transport", "Codec", "Resolution", "PTS", "Error"])
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"[REPORT] Saved camera report to: {report_file}")



def main():
    probe_all_cameras()


if __name__ == "__main__":
    main()

