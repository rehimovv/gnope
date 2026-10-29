"""Deletes files of inactive sessions. Runs at most once a day, piggybacking on
incoming requests, so no cron job is required (python -m app.maintenance also works)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from app.config import Config, load
from app.files import FileStore
from app.storage import Store

log = logging.getLogger(__name__)

DAY = 24 * 60 * 60
UPDATE_ID_TTL = 3 * DAY


def _marker(config: Config) -> Path:
    return config.data_dir / "last_cleanup"


def cleanup(config: Config, store: Store, files: FileStore) -> int:
    now = time.time()
    cutoff = now - config.retention_days * DAY
    removed = 0
    for user_id in store.expired_sessions(int(cutoff)):
        store.delete_session(user_id)
        files.delete_user(user_id)
        removed += 1
    # Pending uploads and leftovers without a session.
    for folder in files.user_dirs():
        try:
            newest = max((p.stat().st_mtime for p in folder.iterdir()), default=0)
        except OSError:  # removed while we looked at it
            continue
        if newest < cutoff and folder.name.isdigit() and store.get_session(int(folder.name)) is None:
            files.delete_user(int(folder.name))
            removed += 1
    store.purge_updates(int(now - UPDATE_ID_TTL))
    _marker(config).write_text(str(int(now)), encoding="ascii")
    return removed


def maybe_cleanup(config: Config, store: Store, files: FileStore) -> None:
    try:
        last = float(_marker(config).read_text(encoding="ascii"))
    except (OSError, ValueError):
        last = 0.0
    if time.time() - last < DAY:
        return
    removed = cleanup(config, store, files)
    if removed:
        log.info("cleanup removed %d inactive file(s)", removed)


if __name__ == "__main__":  # pragma: no cover
    cfg = load()
    count = cleanup(cfg, Store(cfg.data_dir / "bot.db"), FileStore(cfg.data_dir))
    print("removed", count)  # noqa: T201
