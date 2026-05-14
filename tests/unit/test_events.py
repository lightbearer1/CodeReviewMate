"""Tests for event bus."""

from __future__ import annotations

import asyncio

import pytest

from codereviewmate.core.events.bus import EventBus, get_event_bus
from codereviewmate.core.events.events import Event, EventType


class TestEventBus:
    def test_subscribe_and_emit_sync(self):
        """Sync handler should receive events."""
        bus = EventBus()
        received: list[Event] = []

        def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.CONFIG_LOADED, handler)
        event = Event(type=EventType.CONFIG_LOADED, data={"key": "value"})
        bus.emit_sync(event)

        assert len(received) == 1
        assert received[0].type == EventType.CONFIG_LOADED
        assert received[0].data["key"] == "value"

    @pytest.mark.asyncio
    async def test_subscribe_and_emit_async(self):
        """Async handler should receive events."""
        bus = EventBus()
        received: list[Event] = []

        async def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.REVIEW_COMPLETED, handler)
        event = Event(type=EventType.REVIEW_COMPLETED, data={"passed": True})
        await bus.emit(event)

        assert len(received) == 1

    def test_unsubscribe(self):
        """Handler should be removable."""
        bus = EventBus()
        received: list[Event] = []

        def handler(event: Event) -> None:
            received.append(event)

        bus.subscribe(EventType.CONFIG_UPDATED, handler)
        bus.unsubscribe(EventType.CONFIG_UPDATED, handler)
        bus.emit_sync(Event(type=EventType.CONFIG_UPDATED))

        assert len(received) == 0

    def test_multiple_handlers(self):
        """Multiple handlers should all fire."""
        bus = EventBus()
        results = []

        def handler1(e):
            results.append(1)

        def handler2(e):
            results.append(2)

        bus.subscribe(EventType.CONFIG_LOADED, handler1)
        bus.subscribe(EventType.CONFIG_LOADED, handler2)
        bus.emit_sync(Event(type=EventType.CONFIG_LOADED))

        assert results == [1, 2]

    def test_handler_error_doesnt_block_others(self):
        """One handler failing should not affect others."""
        bus = EventBus()
        results = []

        def bad_handler(e):
            raise RuntimeError("oops")

        def good_handler(e):
            results.append("ok")

        bus.subscribe(EventType.CONFIG_LOADED, bad_handler)
        bus.subscribe(EventType.CONFIG_LOADED, good_handler)
        bus.emit_sync(Event(type=EventType.CONFIG_LOADED))

        assert results == ["ok"]
