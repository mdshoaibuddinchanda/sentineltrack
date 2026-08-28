import importlib
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    from ..errors import TargetNotFoundError, DuplicateTargetError, InvalidQueryParameterError, DatabaseUnavailableError
    from ..schemas.targets import TargetCreateRequest, TargetUpdateRequest, TargetResponse, TargetPriorityEnum
except (ImportError, ValueError):
    err_m = importlib.import_module("08_backend.errors")
    TargetNotFoundError = err_m.TargetNotFoundError
    DuplicateTargetError = err_m.DuplicateTargetError
    InvalidQueryParameterError = err_m.InvalidQueryParameterError
    DatabaseUnavailableError = err_m.DatabaseUnavailableError

    tgt_m = importlib.import_module("08_backend.schemas.targets")
    TargetCreateRequest = tgt_m.TargetCreateRequest
    TargetUpdateRequest = tgt_m.TargetUpdateRequest
    TargetResponse = tgt_m.TargetResponse
    TargetPriorityEnum = tgt_m.TargetPriorityEnum


def _get_target_matching_modules():
    p5_models = importlib.import_module("05_target_matching.models")
    p5_watchlist = importlib.import_module("05_target_matching.watchlist")
    p5_repo = importlib.import_module("05_target_matching.repository")
    p5_norm = importlib.import_module("05_target_matching.normalizer")
    return p5_models, p5_watchlist, p5_repo, p5_norm


_GLOBAL_WATCHLIST_MANAGER = None
_WM_LOCK = threading.Lock()


def get_shared_watchlist_manager(repository=None):
    global _GLOBAL_WATCHLIST_MANAGER
    with _WM_LOCK:
        if _GLOBAL_WATCHLIST_MANAGER is None:
            models, watchlist_mod, repo_mod, norm_mod = _get_target_matching_modules()
            repo = repository or repo_mod.PostgresTargetMatchingRepository()
            _GLOBAL_WATCHLIST_MANAGER = watchlist_mod.WatchlistManager(repository=repo)
            try:
                _GLOBAL_WATCHLIST_MANAGER.refresh_cache_from_repository(repo)
            except Exception:
                pass
        return _GLOBAL_WATCHLIST_MANAGER


class TargetService:
    """Service managing target watchlists, registration normalization, and truthful target CRUD."""

    def __init__(self, repository=None, watchlist_manager=None):
        models, watchlist_mod, repo_mod, norm_mod = _get_target_matching_modules()
        self.models = models
        self.norm = norm_mod
        self.repository = repository or repo_mod.PostgresTargetMatchingRepository()
        self.watchlist_manager = watchlist_manager or get_shared_watchlist_manager(self.repository)

    def create_target(self, request: TargetCreateRequest) -> TargetResponse:
        norm_reg, is_valid, err = self.norm.normalize_target_registration(request.registration)
        if not is_valid:
            raise InvalidQueryParameterError(f"Invalid target registration '{request.registration}': {err}")

        # Check existing
        with self.watchlist_manager._lock:
            existing_ids = self.watchlist_manager._exact_index.get(norm_reg, set())
            for eid in existing_ids:
                e = self.watchlist_manager._entries.get(eid)
                if e and e.enabled:
                    raise DuplicateTargetError(
                        f"Target with registration '{norm_reg}' is already actively tracked on the watchlist."
                    )

        priority_enum = self.models.WatchlistPriority(request.priority.value)
        entry, ok, msg = self.watchlist_manager.add_entry(
            registration=request.registration,
            priority=priority_enum,
            expires_at=request.expires_at,
            notes=request.notes,
            metadata=request.metadata
        )

        if not ok or not entry:
            if msg and "Database persistence failure" in msg:
                raise DatabaseUnavailableError(msg)
            raise DuplicateTargetError(msg or "Failed to create target entry.")

        return TargetResponse(
            target_id=entry.watchlist_id,
            registration=entry.registration,
            normalized_registration=entry.normalized_registration,
            priority=entry.priority.value,
            enabled=entry.enabled,
            created_at=entry.created_at,
            expires_at=entry.expires_at,
            notes=entry.notes,
            metadata=entry.metadata
        )

    def list_targets(
        self,
        limit: int = 50,
        offset: int = 0,
        priority: Optional[TargetPriorityEnum] = None,
        enabled: Optional[bool] = None
    ) -> List[TargetResponse]:
        with self.watchlist_manager._lock:
            entries = list(self.watchlist_manager._entries.values())

        if priority:
            entries = [e for e in entries if e.priority.value == priority.value]
        if enabled is not None:
            entries = [e for e in entries if e.enabled == enabled]

        paged = entries[offset : offset + limit]
        return [
            TargetResponse(
                target_id=e.watchlist_id,
                registration=e.registration,
                normalized_registration=e.normalized_registration,
                priority=e.priority.value,
                enabled=e.enabled,
                created_at=e.created_at,
                expires_at=e.expires_at,
                notes=e.notes,
                metadata=e.metadata
            )
            for e in paged
        ]

    def get_target(self, target_id: str) -> TargetResponse:
        entry = self.watchlist_manager.get_entry(target_id)
        if not entry:
            raise TargetNotFoundError(f"Target '{target_id}' not found.")

        return TargetResponse(
            target_id=entry.watchlist_id,
            registration=entry.registration,
            normalized_registration=entry.normalized_registration,
            priority=entry.priority.value,
            enabled=entry.enabled,
            created_at=entry.created_at,
            expires_at=entry.expires_at,
            notes=entry.notes,
            metadata=entry.metadata
        )

    def update_target(self, target_id: str, request: TargetUpdateRequest) -> TargetResponse:
        entry = self.watchlist_manager.get_entry(target_id)
        if not entry:
            raise TargetNotFoundError(f"Target '{target_id}' not found.")

        # Snapshot existing state for rollback if DB persistence fails
        old_priority = entry.priority
        old_enabled = entry.enabled
        old_expires_at = entry.expires_at
        old_notes = entry.notes
        old_metadata = dict(entry.metadata) if entry.metadata else {}

        # Apply prospective changes
        if request.priority:
            entry.priority = self.models.WatchlistPriority(request.priority.value)
        if request.enabled is not None and request.enabled != old_enabled:
            self.watchlist_manager.set_enabled(target_id, request.enabled)
        if request.expires_at is not None:
            entry.expires_at = request.expires_at
        if request.notes is not None:
            entry.notes = request.notes
        if request.metadata is not None:
            entry.metadata.update(request.metadata)

        if self.repository:
            try:
                self.repository.save_watchlist_entry(entry)
            except Exception as e:
                # Rollback in-memory entry on DB persistence failure
                entry.priority = old_priority
                entry.expires_at = old_expires_at
                entry.notes = old_notes
                entry.metadata = old_metadata
                if request.enabled is not None and request.enabled != old_enabled:
                    self.watchlist_manager.set_enabled(target_id, old_enabled)
                raise DatabaseUnavailableError(f"Database persistence failure while updating target: {e}")

        return TargetResponse(
            target_id=entry.watchlist_id,
            registration=entry.registration,
            normalized_registration=entry.normalized_registration,
            priority=entry.priority.value,
            enabled=entry.enabled,
            created_at=entry.created_at,
            expires_at=entry.expires_at,
            notes=entry.notes,
            metadata=entry.metadata
        )

    def disable_target(self, target_id: str) -> TargetResponse:
        entry = self.watchlist_manager.get_entry(target_id)
        if not entry:
            raise TargetNotFoundError(f"Target '{target_id}' not found.")

        old_enabled = entry.enabled
        self.watchlist_manager.set_enabled(target_id, False)

        if self.repository:
            try:
                self.repository.save_watchlist_entry(entry)
            except Exception as e:
                # Rollback in-memory enabled state on DB persistence failure
                self.watchlist_manager.set_enabled(target_id, old_enabled)
                raise DatabaseUnavailableError(f"Database persistence failure while disabling target: {e}")

        return TargetResponse(
            target_id=entry.watchlist_id,
            registration=entry.registration,
            normalized_registration=entry.normalized_registration,
            priority=entry.priority.value,
            enabled=entry.enabled,
            created_at=entry.created_at,
            expires_at=entry.expires_at,
            notes=entry.notes,
            metadata=entry.metadata
        )

