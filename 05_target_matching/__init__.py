from .models import (
    MatchClass,
    WatchlistPriority,
    AlertSeverity,
    TargetRegistration,
    MatchCandidate,
    Sighting,
    TargetMatchRecord,
    WatchlistEntry,
    Alert
)
from .config import TargetMatchingConfig
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
from .repository import (
    BaseTargetMatchingRepository,
    SQLiteTargetMatchingRepository,
    PostgresTargetMatchingRepository,
    get_repository
)
# Alias for backwards compatibility
TargetMatchingRepository = SQLiteTargetMatchingRepository

from .history import HistoricalSearchService

__all__ = [
    'MatchClass',
    'WatchlistPriority',
    'AlertSeverity',
    'TargetRegistration',
    'MatchCandidate',
    'Sighting',
    'TargetMatchRecord',
    'WatchlistEntry',
    'Alert',
    'TargetMatchingConfig',
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
    'BaseTargetMatchingRepository',
    'SQLiteTargetMatchingRepository',
    'PostgresTargetMatchingRepository',
    'TargetMatchingRepository',
    'get_repository',
    'HistoricalSearchService',
    'TargetMatchingPipeline',
]


def __getattr__(name: str):
    if name == 'TargetMatchingPipeline':
        from .pipeline import TargetMatchingPipeline
        return TargetMatchingPipeline
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

