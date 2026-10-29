"""Settings read from the .env file next to the app (and the environment)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

APP_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Config:
    app_root: Path
    data_dir: Path
    bot_token: str
    base_url: str
    max_file_bytes: int
    retention_days: int
    daily_upload_limit: int
    developer_name: str
    developer_url: str
    developer_telegram: str
    source_url: str

    @property
    def webhook_url(self) -> str:
        return self.base_url.rstrip("/") + "/webhook"

    @property
    def base_path(self) -> str:
        """URL path the app is mounted on, e.g. '/tools/poeditor'."""
        without_scheme = self.base_url.split("://", 1)[-1]
        path = "/" + without_scheme.split("/", 1)[1] if "/" in without_scheme else ""
        return path.rstrip("/")


def read_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def load(app_root: Optional[Path] = None, environ: Optional[Mapping[str, str]] = None) -> Config:
    root = app_root or APP_ROOT
    env = dict(read_env_file(root / ".env"))
    env.update({k: v for k, v in (environ if environ is not None else os.environ).items() if k in _KEYS})

    def get(key: str) -> str:
        return env.get(key, "").strip() or _DEFAULTS[key]

    data_dir = Path(get("DATA_DIR"))
    if not data_dir.is_absolute():
        data_dir = root / data_dir
    return Config(
        app_root=root,
        data_dir=data_dir,
        bot_token=env.get("BOT_TOKEN", "").strip(),
        base_url=get("BASE_URL").rstrip("/"),
        max_file_bytes=int(float(get("MAX_FILE_MB")) * 1024 * 1024),
        retention_days=int(get("RETENTION_DAYS")),
        daily_upload_limit=int(get("DAILY_UPLOAD_LIMIT")),
        developer_name=get("DEVELOPER_NAME"),
        developer_url=get("DEVELOPER_URL"),
        developer_telegram=get("DEVELOPER_TELEGRAM").lstrip("@"),
        source_url=get("SOURCE_URL"),
    )


_DEFAULTS = {
    "DATA_DIR": "data",
    "BASE_URL": "https://azelinux.com/tools/poeditor",
    "MAX_FILE_MB": "5",
    "RETENTION_DAYS": "14",
    "DAILY_UPLOAD_LIMIT": "50",
    "DEVELOPER_NAME": "Ramal Rahimov",
    "DEVELOPER_URL": "https://azelinux.com",
    "DEVELOPER_TELEGRAM": "rahimovramal",
    "SOURCE_URL": "https://github.com/rehimovv/gnome-po-telegram-bot",
}
_KEYS = set(_DEFAULTS) | {"BOT_TOKEN"}
