"""Per-update context shared by the handlers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Optional

from app.config import Config
from app.files import FileStore
from app.i18n import DEFAULT, tr
from app.storage import Store, User
from app.telegram import TelegramApi


@dataclass(frozen=True)
class Deps:
    api: TelegramApi
    store: Store
    files: FileStore
    config: Config


@dataclass(frozen=True)
class Ctx:
    deps: Deps
    user: User
    chat_id: int

    @property
    def lang(self) -> str:
        return self.user.ui_lang or DEFAULT

    def t(self, msgid: str, **values: Any) -> str:
        return tr(self.lang, msgid, **values)

    def send(self, text: str, keyboard: Optional[dict] = None) -> int:
        return self.deps.api.send_message(self.chat_id, text, keyboard)

    def update_user(self, **changes: Any) -> "Ctx":
        user = self.deps.store.save_user(replace(self.user, **changes))
        return replace(self, user=user)

    def set_state(self, state: str, **data: Any) -> "Ctx":
        return self.update_user(state=state, state_data=dict(data))

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)
