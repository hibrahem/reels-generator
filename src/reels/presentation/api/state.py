"""Application state shared across requests: the active config path + a cached Container."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from reels.presentation.container import Container


class AppState:
    """Holds the active config path and a cached Container, rebuilt when config changes."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self._container: Container | None = None

    @property
    def container(self) -> Container:
        if self._container is None:
            self._container = Container.from_config(self.config_path)
        return self._container

    def reload(self) -> Container:
        self._container = Container.from_config(self.config_path)
        return self._container


def get_state(request: Request) -> AppState:
    return request.app.state.reels
