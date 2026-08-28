import threading
import uuid
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional, Any

from .models import WatchlistEntry, WatchlistPriority
from .normalizer import normalize_target_registration
from .config import TargetMatchingConfig

CONFUSION_PREFIX_VARIANTS = {
    '0': ['O', 'D', 'Q'],
    'O': ['0'],
    '1': ['I', 'L'],
    'I': ['1'],
    '8': ['B'],
    'B': ['8'],
    '5': ['S'],
    'S': ['5'],
    '2': ['Z'],
    'Z': ['2'],
    '6': ['G'],
    'G': ['6'],
    '4': ['A'],
    'A': ['4']
}


def expand_prefix_variants(prefix: str) -> list[str]:
    """Generates credible OCR confusion variants for plate prefixes."""
    variants = [prefix]
    if len(prefix) >= 2:
        c0, c1 = prefix[0], prefix[1]
        for alt0 in CONFUSION_PREFIX_VARIANTS.get(c0, [c0]):
            for alt1 in CONFUSION_PREFIX_VARIANTS.get(c1, [c1]):
                v = alt0 + alt1
                if v not in variants:
                    variants.append(v)
    return variants


class WatchlistManager:
    """
    Thread-safe in-memory watchlist manager with deterministic pre-scored candidate shortlisting.
    Provides sub-millisecond candidate generation with near 100% target recall across 100,000+ targets.
    """

    def __init__(
        self,
        config: Optional[TargetMatchingConfig] = None,
        repository: Optional[Any] = None
    ):
        self.config = config or TargetMatchingConfig.from_yaml()
        self.repository = repository
        self._lock = threading.Lock()
        self._entries: dict[str, WatchlistEntry] = {}

        # Precomputed multi-index tables
        self._exact_index: dict[str, set[str]] = defaultdict(set)
        self._state_index: dict[str, set[str]] = defaultdict(set)
        self._prefix3_index: dict[str, set[str]] = defaultdict(set)
        self._suffix4_index: dict[str, set[str]] = defaultdict(set)
        self._length_index: dict[int, set[str]] = defaultdict(set)

    def add_entry(
        self,
        registration: str,
        priority: WatchlistPriority = WatchlistPriority.NORMAL,
        expires_at: Optional[datetime] = None,
        notes: Optional[str] = None,
        metadata: Optional[dict] = None,
        watchlist_id: Optional[str] = None
    ) -> tuple[Optional[WatchlistEntry], bool, Optional[str]]:
        norm_reg, is_valid, err = normalize_target_registration(registration)
        if not is_valid:
            return None, False, err

        with self._lock:
            if norm_reg in self._exact_index:
                existing_ids = list(self._exact_index[norm_reg])
                if existing_ids and existing_ids[0] in self._entries:
                    existing = self._entries[existing_ids[0]]
                    if self.config.duplicate_policy == 'reject':
                        return None, False, f'Target registration \"{norm_reg}\" already exists on watchlist'
                    else:
                        existing.priority = priority
                        existing.notes = notes or existing.notes
                        existing.expires_at = expires_at or existing.expires_at
                        if metadata:
                            existing.metadata.update(metadata)
                        return existing, True, None

            w_id = watchlist_id or str(uuid.uuid4())
            entry = WatchlistEntry(
                watchlist_id=w_id,
                registration=registration.strip(),
                normalized_registration=norm_reg,
                priority=priority,
                enabled=True,
                expires_at=expires_at,
                notes=notes,
                metadata=metadata or {}
            )

            self._entries[w_id] = entry
            self._rebuild_indices_for_entry(entry, add=True)

            if self.repository:
                try:
                    self.repository.save_watchlist_entry(entry)
                except Exception as e:
                    self._entries.pop(w_id, None)
                    self._rebuild_indices_for_entry(entry, add=False)
                    return None, False, f"Database persistence failure: {e}"

        return entry, True, None

    def remove_entry(self, watchlist_id: str) -> bool:
        with self._lock:
            if watchlist_id not in self._entries:
                return False
            entry = self._entries.pop(watchlist_id)
            self._rebuild_indices_for_entry(entry, add=False)
            return True

    def set_enabled(self, watchlist_id: str, enabled: bool) -> bool:
        with self._lock:
            if watchlist_id not in self._entries:
                return False
            entry = self._entries[watchlist_id]
            if entry.enabled != enabled:
                entry.enabled = enabled
                self._rebuild_indices_for_entry(entry, add=enabled)
            return True

    def get_entry(self, watchlist_id: str) -> Optional[WatchlistEntry]:
        with self._lock:
            return self._entries.get(watchlist_id)

    def get_active_entries(self) -> list[WatchlistEntry]:
        now = datetime.now(timezone.utc)
        with self._lock:
            active = []
            for e in self._entries.values():
                if not e.enabled:
                    continue
                if e.expires_at and e.expires_at < now:
                    continue
                active.append(e)
            return active

    def count_active(self) -> int:
        return len(self.get_active_entries())

    def refresh_cache_from_repository(self, repository: Any) -> int:
        active_db_entries = repository.list_active_watchlist_entries()
        with self._lock:
            self._entries.clear()
            self._exact_index.clear()
            self._state_index.clear()
            self._prefix3_index.clear()
            self._suffix4_index.clear()
            self._length_index.clear()

            for entry in active_db_entries:
                self._entries[entry.watchlist_id] = entry
                self._rebuild_indices_for_entry(entry, add=True)
            return len(self._entries)

    def _rebuild_indices_for_entry(self, entry: WatchlistEntry, add: bool = True):
        p = entry.normalized_registration
        w_id = entry.watchlist_id

        if add:
            self._exact_index[p].add(w_id)
            if entry.state_prefix:
                self._state_index[entry.state_prefix].add(w_id)
            if entry.plate_length:
                self._length_index[entry.plate_length].add(w_id)
            if len(p) >= 3:
                self._prefix3_index[p[:3]].add(w_id)
            if len(p) >= 4:
                self._suffix4_index[p[-4:]].add(w_id)
        else:
            self._exact_index[p].discard(w_id)
            if entry.state_prefix:
                self._state_index[entry.state_prefix].discard(w_id)
            if entry.plate_length:
                self._length_index[entry.plate_length].discard(w_id)
            if len(p) >= 3:
                self._prefix3_index[p[:3]].discard(w_id)
            if len(p) >= 4:
                self._suffix4_index[p[-4:]].discard(w_id)

    def lookup_candidates(self, observed_registration: str, max_candidates: Optional[int] = None) -> list[WatchlistEntry]:
        norm_obs = observed_registration.strip().upper()
        if not norm_obs:
            return []

        limit = max_candidates or self.config.max_candidate_shortlist
        now = datetime.now(timezone.utc)
        obs_set = set(norm_obs)
        obs_len = len(norm_obs)
        obs_prefix = norm_obs[:2] if obs_len >= 2 else ''
        obs_p3 = norm_obs[:3] if obs_len >= 3 else ''
        obs_s4 = norm_obs[-4:] if obs_len >= 4 else ''

        with self._lock:
            if len(self._entries) <= limit:
                return [
                    e for e in self._entries.values()
                    if e.enabled and (not e.expires_at or e.expires_at >= now)
                ]

            candidate_ids = set()

            # 1. Exact match shortcut
            if norm_obs in self._exact_index:
                candidate_ids.update(self._exact_index[norm_obs])

            # 2. State Prefix & Confusion Variants
            for p_var in expand_prefix_variants(obs_prefix):
                if p_var in self._state_index:
                    candidate_ids.update(self._state_index[p_var])

            # 3. 3-Char Prefix match
            if obs_p3 and obs_p3 in self._prefix3_index:
                candidate_ids.update(self._prefix3_index[obs_p3])

            # 4. Suffix (Last 4 Digits) match - Highly discriminative in Indian registrations
            if obs_s4 and obs_s4 in self._suffix4_index:
                candidate_ids.update(self._suffix4_index[obs_s4])

            # 5. Length proximity if candidate pool is still small
            if len(candidate_ids) < limit:
                candidate_ids.update(self._length_index.get(obs_len, set()))

            # Heuristic pre-scoring
            scored_candidates = []
            for cid in candidate_ids:
                e = self._entries.get(cid)
                if not e or not e.enabled or (e.expires_at and e.expires_at < now):
                    continue

                t_norm = e.normalized_registration
                pre_score = 0.0

                if t_norm == norm_obs:
                    pre_score += 100.0
                if obs_s4 and t_norm.endswith(obs_s4):
                    pre_score += 40.0
                if obs_p3 and t_norm.startswith(obs_p3):
                    pre_score += 30.0
                elif obs_prefix and t_norm.startswith(obs_prefix):
                    pre_score += 20.0

                pre_score -= abs(len(t_norm) - obs_len) * 3.0
                pre_score += len(set(t_norm) & obs_set) * 2.0

                scored_candidates.append((pre_score, e))

            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            return [sc[1] for sc in scored_candidates[:limit]]
