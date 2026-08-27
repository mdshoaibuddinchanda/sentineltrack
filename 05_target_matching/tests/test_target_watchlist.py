import importlib
from datetime import datetime, timezone, timedelta

wl_mod = importlib.import_module('05_target_matching.watchlist')
models_mod = importlib.import_module('05_target_matching.models')
WatchlistManager = wl_mod.WatchlistManager
WatchlistPriority = models_mod.WatchlistPriority


def test_watchlist_add_and_get():
    wm = WatchlistManager()
    entry, ok, err = wm.add_entry(
        registration='GJ01AB1234',
        priority=WatchlistPriority.HIGH,
        notes='Stolen vehicle alert'
    )
    assert ok is True
    assert entry.normalized_registration == 'GJ01AB1234'
    assert wm.count_active() == 1

    fetched = wm.get_entry(entry.watchlist_id)
    assert fetched is not None
    assert fetched.priority == WatchlistPriority.HIGH


def test_watchlist_enable_disable():
    wm = WatchlistManager()
    entry, _, _ = wm.add_entry('MH12DE1432')
    assert wm.count_active() == 1

    wm.set_enabled(entry.watchlist_id, False)
    assert wm.count_active() == 0

    wm.set_enabled(entry.watchlist_id, True)
    assert wm.count_active() == 1


def test_watchlist_expiry():
    wm = WatchlistManager()
    past_time = datetime.now(timezone.utc) - timedelta(hours=1)
    future_time = datetime.now(timezone.utc) + timedelta(hours=1)

    wm.add_entry('DL01AB9999', expires_at=past_time)
    wm.add_entry('KA05NB1234', expires_at=future_time)

    active = wm.get_active_entries()
    assert len(active) == 1
    assert active[0].normalized_registration == 'KA05NB1234'


def test_watchlist_fast_shortlisting():
    wm = WatchlistManager()
    wm.add_entry('GJ01AB1234')
    wm.add_entry('GJ01AB5678')
    wm.add_entry('DL04CD9999')

    # Look up candidates for 'GJ01A81234'
    candidates = wm.lookup_candidates('GJ01A81234')
    c_regs = {c.normalized_registration for c in candidates}
    assert 'GJ01AB1234' in c_regs
