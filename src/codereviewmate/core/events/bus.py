"""Lightweight event bus (pub/sub) for inter-layer communication."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

from codereviewmate.core.events.events import Event, EventType

logger = logging.getLogger(__name__)

AsyncHandler = Callable[[Event], Coroutine[Any, Any, None]]
SyncHandler = Callable[[Event], None]
Handler = AsyncHandler | SyncHandler


class EventBus:
    """A simple in-process event bus supporting sync and async handlers."""

    def __init__(self):
        self._handlers: dict[EventType, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: Handler) -> None:
        """Register a handler for an event type."""
        self._handlers[event_type].append(handler)
        logger.debug("Subscribed %s to %s", handler.__name__, event_type.value)

    def unsubscribe(self, event_type: EventType, handler: Handler) -> None:
        """Remove a handler from an event type."""
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug("Unsubscribed %s from %s", handler.__name__, event_type.value)

    async def emit(self, event: Event) -> None:
        """Emit an event to all registered handlers."""
        handlers = self._handlers.get(event.type, [])
        if not handlers:
            logger.debug("No handlers for event %s", event.type.value)
            return

        logger.info("Emitting %s with %d handlers", event.type.value, len(handlers))
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                logger.exception(
                    "Handler %s failed for event %s", handler.__name__, event.type.value
                )

    def emit_sync(self, event: Event) -> None:
        """Synchronous emit for contexts without a running event loop."""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.run(handler(event))
                else:
                    handler(event)
            except Exception:
                logger.exception(
                    "Handler %s failed for event %s", handler.__name__, event.type.value
                )


_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global event bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
