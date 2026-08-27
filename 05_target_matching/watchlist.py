import threading
import uuid
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional

from .models import WatchlistEntry, WatchlistPriority
from .normalizer import normalize_target_registration


class WatchlistManager:
    """
    Thread-safe in-memory watchlist manager with multi-index candidate shortlisting.
    Provides sub-millisecond candidate generation for large target registries.
    """

    def __init__(self):
        self._lock = threading.RWMutex() if hasattr(threading, 'RWMutex') else threading.Lock()
        self._entries: dict[str, WatchlistEntry] = {}

        # Precomputed index tables
        self._exact_index: dict[str, set[str]] = defaultdict(set)
        self._state_index: dict[str, set[str]] = defaultdict(set)
        self._length_index: dict[int, set[str]] = defaultdict(set)
        self._prefix3_index: dict[str, set[str]] = defaultdict(set)

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

        with self._lock:
            self._entries[w_id] = entry
            self._rebuild_indices_for_entry(entry, add=True)

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
        else:
            self._exact_index[p].discard(w_id)
            if entry.state_prefix:
                self._state_index[entry.state_prefix].discard(w_id)
            if entry.plate_length:
                self._length_index[entry.plate_length].discard(w_id)
            if len(p) >= 3:
                self._prefix3_index[p[:3]].discard(w_id)

    def lookup_candidates(self, observed_registration: str, max_candidates: int = 100) -> list[WatchlistEntry]:
        """
        Fast multi-index candidate shortlisting.
        Generates candidates matching exact strings, state codes, length proximity, or prefix match.
        """
        norm_obs = observed_registration.strip().upper()
        if not norm_obs:
            return []

        now = datetime.now(timezone.utc)

        with self._lock:
            candidate_ids = set()

            # 1. Exact Match Shortcut
            if norm_obs in self._exact_index:
                candidate_ids.update(self._exact_index[norm_obs])

            # 2. State Prefix match (e.g. 'GJ')
            if len(norm_obs) >= 2:
                prefix = norm_obs[:2]
                if prefix in self._state_index:
                    candidate_ids.update(self._state_index[prefix])

            # 3. 3-Char Prefix match
            if len(norm_obs) >= 3:
                p3 = norm_obs[:3]
                if p3 in self._prefix3_index:
                    candidate_ids.update(self._prefix3_index[p3])

            # 4. Length proximity (+/- 1 character) if candidate count is small
            if len(candidate_ids) < 10:
                l = len(norm_obs)
                candidate_ids.update(self._length_index.get(l, set()))
                candidate_ids.update(self._length_index.get(l - 1, set()))
                candidate_ids.update(self._length_index.get(l + 1, set()))

            # If watchlist is small (<= 250), fallback to all active entries
            if len(self._entries) <= 250:
                candidate_ids.update(self._entries.keys())

            candidates = []
            for cid in candidate_ids:
                if cid in self._entries:
                    e = self._entries[cid]
                    if e.enabled and (not e.expires_at or e.expires_at >= now):
                        candidates.append(e)

            return candidates[:max_candidates]
