try:
    from .models import VehicleTrack
    from .track_manager import TrackState, TrackManager
    from .tracker import CameraByteTracker, CameraTrackerRegistry, DetectionBoxesAdapter
    from .pipeline import VehicleTrackingPipeline
except (ImportError, ValueError):
    import importlib
    VehicleTrack = importlib.import_module('02_tracking.models').VehicleTrack
    tm = importlib.import_module('02_tracking.track_manager')
    TrackState, TrackManager = tm.TrackState, tm.TrackManager
    tr = importlib.import_module('02_tracking.tracker')
    CameraByteTracker, CameraTrackerRegistry, DetectionBoxesAdapter = tr.CameraByteTracker, tr.CameraTrackerRegistry, tr.DetectionBoxesAdapter
    VehicleTrackingPipeline = importlib.import_module('02_tracking.pipeline').VehicleTrackingPipeline

__all__ = [
    'VehicleTrack',
    'TrackState',
    'TrackManager',
    'CameraByteTracker',
    'CameraTrackerRegistry',
    'DetectionBoxesAdapter',
    'VehicleTrackingPipeline',
]
