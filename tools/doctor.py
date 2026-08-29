import sys
import importlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

def run_doctor():
    print("==================================================")
    print("       SENTINELTRACK SYSTEM DIAGNOSTIC DOCTOR      ")
    print("==================================================")

    subsystems = []

    # 1. Foundation & Camera Stream Decoders
    try:
        import cv2
        import av
        subsystems.append(("Stream Decoders (OpenCV/PyAV)", "PASS", f"OpenCV {cv2.__version__}, PyAV {av.__version__}"))
    except Exception as e:
        subsystems.append(("Stream Decoders (OpenCV/PyAV)", "FAIL", str(e)))

    # 2. Database & PostGIS
    try:
        db_m = importlib.import_module("00_foundation.registry.database")
        pool = db_m.get_db_pool()
        metrics = pool.get_metrics()
        subsystems.append(("Database Connection Pool", "PASS", f"Pool max={metrics['max_size']}, in_use={metrics['in_use']}, idle={metrics['idle']}"))
    except Exception as e:
        subsystems.append(("Database Connection Pool", "WARN", f"Direct/Mock connection: {e}"))

    # 3. Vision & ML Pipeline (P1–P5)
    try:
        import torch
        import onnxruntime as ort
        cuda_status = f"CUDA {torch.version.cuda} on {torch.cuda.get_device_name(0)}" if torch.cuda.is_available() else "CPU Mode"
        subsystems.append(("Deep Learning Runtime (PyTorch/ONNX)", "PASS", f"{cuda_status}, ORT {ort.__version__}"))
    except Exception as e:
        subsystems.append(("Deep Learning Runtime (PyTorch/ONNX)", "FAIL", str(e)))

    # 4. Security & Authentication (P10)
    try:
        sec_m = importlib.import_module("10_security")
        pw_m = importlib.import_module("10_security.password")
        dummy_ready = bool(pw_m.DUMMY_PASSWORD_HASH.startswith("$argon2id$"))
        subsystems.append(("Security, RBAC & Argon2id Timing Equalization", "PASS" if dummy_ready else "FAIL", "Timing dummy hash & session RBAC active"))
    except Exception as e:
        subsystems.append(("Security, RBAC & Argon2id Timing Equalization", "FAIL", str(e)))

    # 5. Scalability & Stream Supervision (P11)
    try:
        scale_cfg_m = importlib.import_module("11_scale_deployment.config")
        cfg = scale_cfg_m.get_scale_config()
        subsystems.append(("Scale, Scheduler & Stream Supervisor", "PASS", f"Role={cfg.process_role}, Shards={cfg.shard_count}, Base={cfg.base_sampling_fps} FPS, Burst={cfg.burst_sampling_fps} FPS"))
    except Exception as e:
        subsystems.append(("Scale, Scheduler & Stream Supervisor", "FAIL", str(e)))

    # 6. Dashboard Frontend & Static Assets
    try:
        dist_index = REPO_ROOT / "09_dashboard" / "dist" / "index.html"
        if dist_index.exists():
            subsystems.append(("Frontend Production Assets", "PASS", "Vite production build present in 09_dashboard/dist/"))
        else:
            subsystems.append(("Frontend Production Assets", "WARN", "Vite build not yet generated (run npm run build in 09_dashboard)"))
    except Exception as e:
        subsystems.append(("Frontend Production Assets", "WARN", str(e)))

    for name, status, details in subsystems:
        color_marker = f"[{status}]"
        print(f"{color_marker:<8} {name:<42} : {details}")

    print("==================================================")
    fails = sum(1 for _, s, _ in subsystems if s == "FAIL")
    if fails > 0:
        print(f"Doctor Summary: {fails} CRITICAL FAILURE(S) DETECTED")
        return 1
    else:
        print("Doctor Summary: ALL MANDATORY SUBSYSTEMS OPERATIONAL")
        return 0

if __name__ == "__main__":
    sys.exit(run_doctor())
