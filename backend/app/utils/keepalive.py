"""
WebSocket keepalive utility functions.

Provides application-level heartbeat (ping/pong) and idle monitoring
to keep meeting WebSocket connections alive and detect stale connections.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


async def send_keepalive(
    websocket: Any, interval: int, stop_event: asyncio.Event
) -> None:
    """
    Send periodic ping messages to keep WebSocket connection alive.

    Args:
        websocket: WebSocket connection to send pings on
        interval: Seconds between ping messages
        stop_event: Event to signal stopping the keepalive loop
    """
    logger.info(f"Starting keepalive sender with interval={interval}s")

    while not stop_event.is_set():
        try:
            await asyncio.sleep(interval)

            if stop_event.is_set():
                break

            # Send application-level ping
            await websocket.send_json(
                {
                    "type": "ping",
                    "ts": time.time(),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            logger.debug(f"Sent keepalive ping")

        except asyncio.CancelledError:
            logger.info("Keepalive sender cancelled")
            break
        except Exception as e:
            logger.warning(f"Keepalive send error: {e}")
            # Connection likely closed, stop the loop
            break

    logger.info("Keepalive sender stopped")


async def idle_monitor(
    websocket: Any, max_idle: int, last_received_ref: list, stop_event: asyncio.Event
) -> None:
    """
    Monitor connection for idle timeout and close if exceeded.

    Args:
        websocket: WebSocket connection to monitor
        max_idle: Maximum idle time in seconds before closing
        last_received_ref: List containing [last_received_timestamp] as a mutable reference
        stop_event: Event to signal stopping the monitor
    """
    logger.info(f"Starting idle monitor with max_idle={max_idle}s")
    check_interval = min(30, max_idle // 2)  # Check at least twice within max_idle

    while not stop_event.is_set():
        try:
            await asyncio.sleep(check_interval)

            if stop_event.is_set():
                break

            # Check idle time
            current_time = time.time()
            last_received = last_received_ref[0]
            idle_time = current_time - last_received

            logger.debug(f"Idle check: {idle_time:.1f}s / {max_idle}s")

            if idle_time > max_idle:
                logger.warning(
                    f"Connection idle for {idle_time:.1f}s, closing (max={max_idle}s)"
                )
                try:
                    await websocket.send_json(
                        {
                            "type": "idle_timeout",
                            "message": f"Connection closed due to {max_idle}s inactivity",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                    await asyncio.sleep(0.1)  # Give time for message to send
                    await websocket.close(code=1000, reason="idle_timeout")
                except Exception as e:
                    logger.debug(f"Error closing idle connection: {e}")
                break

        except asyncio.CancelledError:
            logger.info("Idle monitor cancelled")
            break
        except Exception as e:
            logger.warning(f"Idle monitor error: {e}")
            break

    logger.info("Idle monitor stopped")
