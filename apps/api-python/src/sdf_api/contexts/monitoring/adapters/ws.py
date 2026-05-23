"""WebSocket fan-out for live line-state push (boundary adapter).

:class:`LineStateBroadcaster` is an in-memory pub/sub over asyncio queues;
:func:`register_ws` binds the ``/ws/line-state`` endpoint that streams published
payloads to every connected client. A slow consumer (full queue) drops the
current message rather than blocking the publisher. No upward imports
(``adapters-no-upward``, ADR-0023 #6) — the composition root owns the poller that
feeds the broadcaster.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

_QUEUE_MAXSIZE = 64


class LineStateBroadcaster:
    def __init__(self) -> None:
        self._subscribers: list[asyncio.Queue[dict[str, object]]] = []
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue[dict[str, object]]:
        queue: asyncio.Queue[dict[str, object]] = asyncio.Queue(maxsize=_QUEUE_MAXSIZE)
        self._subscribers.append(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, object]]) -> None:
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    async def publish(self, payload: dict[str, object]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            if queue.full():
                continue  # drop for slow consumers rather than block the publisher
            await queue.put(payload)


def register_ws(app: FastAPI, broadcaster: LineStateBroadcaster) -> None:
    @app.websocket("/ws/line-state")
    async def ws_line_state(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = broadcaster.subscribe()
        try:
            while True:
                payload = await queue.get()
                await websocket.send_json(payload)
        except WebSocketDisconnect:
            pass
        finally:
            await broadcaster.unsubscribe(queue)
