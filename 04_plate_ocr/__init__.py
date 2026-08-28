from .models import OCRHypothesis, TrackOCRResult
from .normalization import normalize_plate_text
from .grammar import score_indian_grammar
from .voting import MultiFramePlateVoter

__all__ = [
    'OCRHypothesis',
    'TrackOCRResult',
    'normalize_plate_text',
    'score_indian_grammar',
    'MultiFramePlateVoter',
    'PlateOCRPipeline',
]


def __getattr__(name: str):
    if name == 'PlateOCRPipeline':
        from .pipeline import PlateOCRPipeline
        return PlateOCRPipeline
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

