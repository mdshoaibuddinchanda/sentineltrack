import sys
import time
import cv2

try:
    from ..streams.reader import RTSPReader
    from ..registry.database import get_camera
except (ImportError, ValueError):
    from streams.reader import RTSPReader
    from registry.database import get_camera


def main():
    if len(sys.argv) != 2:
        print("Usage:")
        print("  python -m 00_foundation.scripts.watch_camera <camera_id_or_stream_url>")
        print("Examples:")
        print("  python -m 00_foundation.scripts.watch_camera 1")
        print("  python -m 00_foundation.scripts.watch_camera http://<HOST>:<PORT>/live/stream/1/index.m3u8")

        return

    arg = sys.argv[1]
    url = arg
    camera_id = arg

    if not (arg.startswith("rtsp://") or arg.startswith("http://") or arg.startswith("https://")):
        cam = get_camera(arg)
        if not cam:
            print(f"[ERROR] Camera ID '{arg}' not found in registry.")
            return
        camera_id = cam["camera_id"]
        from ..streams.resolver import resolve_stream
        url, transport = resolve_stream(cam)
        if not url:
            print(f"[ERROR] No stream URL found for camera '{camera_id}'.")
            return
        print(f"[INFO] Playing Camera {camera_id} via {transport}: {url}")
    else:
        print(f"[INFO] Playing stream: {url}")


    reader = RTSPReader(url=url, camera_id=str(camera_id))

    fps_count = 0
    fps_start = time.perf_counter()
    measured_fps = 0.0

    for frame, pts_ms in reader.frames():
        fps_count += 1
        elapsed = time.perf_counter() - fps_start
        if elapsed >= 1.0:
            measured_fps = fps_count / elapsed
            fps_count = 0
            fps_start = time.perf_counter()

        overlay = f"Camera: {camera_id} | PTS: {pts_ms:.1f}ms | Epoch: {reader.stream_epoch} | FPS: {measured_fps:.1f}"
        cv2.rectangle(frame, (10, 10), (750, 45), (0, 0, 0), -1)
        cv2.putText(frame, overlay, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2)

        cv2.imshow(f"Sentinel Stream — Camera {camera_id}", frame)
        if (cv2.waitKey(1) & 0xFF) == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()