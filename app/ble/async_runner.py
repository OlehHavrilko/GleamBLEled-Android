from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import Any


class AsyncioThread:
    """Runs an asyncio event loop in a dedicated background thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._thread.start()
        self._started = True

    def submit(self, coro: Coroutine[Any, Any, Any]) -> Future[Any]:
        if not self._started:
            self.start()
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self) -> None:
        if not self._started:
            return
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
        self._started = False

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
