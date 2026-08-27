from .models import (
    MatchClass,
    WatchlistPriority,
    AlertSeverity,
    TargetRegistration,
    MatchCandidate,
    Sighting,
    WatchlistEntry,
    Alert
)
from .normalizer import normalize_target_registration, normalize_search_query
from .distance import (
    is_exact_match,
    standard_levenshtein,
    damerau_levenshtein,
    position_weighted_edit_distance
)
from .scorer import TargetMatchScorer
from .watchlist import WatchlistManager
from .alerts import AlertManager, calculate_alert_severity
from .repository import TargetMatchingRepository
from .history import HistoricalSearchService
from .pipeline import TargetMatchingPipeline

__all__ = [
    'MatchClass',
    'WatchlistPriority',
    'AlertSeverity',
    'TargetRegistration',
    'MatchCandidate',
    'Sighting',
    'WatchlistEntry',
    'Alert',
    'normalize_target_registration',
    'normalize_search_query',
    'is_exact_match',
    'standard_levenshtein',
    'damerau_levenshtein',
    'position_weighted_edit_distance',
    'TargetMatchScorer',
    'WatchlistManager',
    'AlertManager',
    'calculate_alert_severity',
    'TargetMatchingRepository',
    'HistoricalSearchService',
    'TargetMatchingPipeline',
]
