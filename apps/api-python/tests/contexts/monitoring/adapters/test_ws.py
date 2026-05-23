"""Tests for the line-state WebSocket broadcaster (the testable WS logic)."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from sdf_api.contexts.monitoring.adapters.ws import LineStateBroadcaster, register_ws

_QUEUE_MAXSIZE = 64


async def test_publish_fans_out_to_all_subscribers() -> None:
    broadcaster = LineStateBroadcaster()
    first = broadcaster.subscribe()
    second = broadcaster.subscribe()
    payload: dict[str, object] = {"lineId": "line-a", "state": "RUNNING"}

    await broadcaster.publish(payload)

    assert await asyncio.wait_for(first.get(), timeout=1.0) == payload
    assert await asyncio.wait_for(second.get(), timeout=1.0) == payload


async def test_publish_drops_message_for_a_full_subscriber() -> None:
    broadcaster = LineStateBroadcaster()
    queue = broadcaster.subscribe()
    for index in range(_QUEUE_MAXSIZE):
        queue.put_nowait({"n": index})

    # A full queue must be skipped, not awaited — the publisher never blocks.
    await asyncio.wait_for(broadcaster.publish({"late": True}), timeout=1.0)

    drained = [queue.get_nowait() for _ in range(_QUEUE_MAXSIZE)]
    assert {"late": True} not in drained


async def test_unsubscribe_stops_delivery() -> None:
    broadcaster = LineStateBroadcaster()
    queue = broadcaster.subscribe()
    await broadcaster.unsubscribe(queue)

    await broadcaster.publish({"lineId": "line-a"})

    assert queue.empty()


def test_register_ws_binds_the_endpoint() -> None:
    app = FastAPI()
    register_ws(app, LineStateBroadcaster())
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/ws/line-state" in paths
