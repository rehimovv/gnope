"""Per-user working files and a per-user lock, kept outside the web root."""

from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Tuple

try:  # Linux hosting; the lock is a no-op on platforms without fcntl
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class FileStore:
    def __init__(self, data_dir: Path) -> None:
        self._root = data_dir / "files"
        self._locks = data_dir / "locks"
        self._root.mkdir(parents=True, exist_ok=True)
        self._locks.mkdir(parents=True, exist_ok=True)

    def _dir(self, user_id: int) -> Path:
        path = self._root / str(int(user_id))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write(self, path: Path, data: bytes) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(data)
        os.replace(str(tmp), str(path))

    def write_work(self, user_id: int, data: bytes) -> None:
        self._write(self._dir(user_id) / "work.po", data)

    def read_work(self, user_id: int) -> Optional[bytes]:
        path = self._dir(user_id) / "work.po"
        return path.read_bytes() if path.is_file() else None

    def write_pending(self, user_id: int, file_name: str, data: bytes) -> None:
        """Keep an uploaded file until the user finishes a question about it."""
        self._write(self._dir(user_id) / "pending.po", data)
        self._write(self._dir(user_id) / "pending.name", file_name.encode("utf-8"))

    def read_pending(self, user_id: int) -> Optional[Tuple[str, bytes]]:
        data = self._dir(user_id) / "pending.po"
        name = self._dir(user_id) / "pending.name"
        if not (data.is_file() and name.is_file()):
            return None
        return name.read_text(encoding="utf-8"), data.read_bytes()

    def drop_pending(self, user_id: int) -> None:
        for name in ("pending.po", "pending.name"):
            path = self._dir(user_id) / name
            if path.is_file():
                path.unlink()

    def delete_user(self, user_id: int) -> None:
        shutil.rmtree(str(self._root / str(int(user_id))), ignore_errors=True)

    def user_dirs(self) -> Iterator[Path]:
        return (p for p in self._root.iterdir() if p.is_dir())

    @contextmanager
    def lock(self, user_id: int) -> Iterator[None]:
        """Serialize updates from one user (Passenger may run several processes)."""
        if fcntl is None:
            yield
            return
        with open(str(self._locks / "{}.lock".format(int(user_id))), "w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
