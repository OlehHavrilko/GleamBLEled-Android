from __future__ import annotations

import json
from pathlib import Path

from app.models import AppState


class ConfigStore:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def load(self) -> AppState:
        if not self._config_path.exists():
            return AppState()

        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return AppState()

        if not isinstance(data, dict):
            return AppState()

        return AppState.from_dict(data)

    def save(self, state: AppState) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        payload = state.to_dict()
        self._config_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
