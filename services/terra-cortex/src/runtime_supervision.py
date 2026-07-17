"""Fail-fast supervision for Terra-Cortex critical background tasks."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional

logger = logging.getLogger(__name__)

FATAL_TASK_EXIT_DELAY_SECONDS = float(
    os.getenv("CORTEX_FATAL_TASK_EXIT_DELAY_SECONDS", "5")
)

CRITICAL_TASK_REASONS = {
    "kafka_consumer_task": "KAFKA_CONSUMER_TASK_STOPPED",
    "dedupe_marker_follower": "DEDUPE_MARKER_FOLLOWER_STOPPED",
    "dedupe_expiry_sweep": "DEDUPE_EXPIRY_SWEEP_STOPPED",
}


def _terminate_process() -> None:
    """Ask the ASGI server to perform its normal SIGTERM shutdown path."""

    os.kill(os.getpid(), signal.SIGTERM)


class CriticalTaskSupervisor:
    """Convert an unexpected critical task exit into a process restart signal."""

    def __init__(
        self,
        *,
        exit_delay_seconds: float = FATAL_TASK_EXIT_DELAY_SECONDS,
        terminate_fn: Callable[[], None] = _terminate_process,
        sleep_fn: Callable[[float], Any] = asyncio.sleep,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        if exit_delay_seconds < 0:
            raise ValueError("fatal task exit delay must not be negative")
        self.exit_delay_seconds = exit_delay_seconds
        self._terminate_fn = terminate_fn
        self._sleep_fn = sleep_fn
        self._now_fn = now_fn

        self.fatal_reason: Optional[str] = None
        self.last_failure_time: Optional[datetime] = None
        self.critical_task_failures = 0
        self._stopping = False
        self._termination_task: Optional[asyncio.Task[Any]] = None
        self._watched_tasks: Dict[str, asyncio.Task[Any]] = {}

    @property
    def fatal(self) -> bool:
        return self.fatal_reason is not None

    @property
    def termination_scheduled(self) -> bool:
        return self._termination_task is not None and not self._termination_task.done()

    def prepare_start(self) -> None:
        self._stopping = False
        self.fatal_reason = None
        self.last_failure_time = None
        self._watched_tasks = {}

    def watch(self, tasks: Mapping[str, Any]) -> None:
        missing = [name for name, task in tasks.items() if task is None]
        if missing:
            raise RuntimeError(
                "critical runtime tasks were not created: " + ", ".join(missing)
            )

        for name, task in tasks.items():
            if name not in CRITICAL_TASK_REASONS:
                raise ValueError(f"unsupported critical task: {name}")
            if not hasattr(task, "add_done_callback"):
                raise TypeError(f"critical task {name} is not an asyncio task")
            self._watched_tasks[name] = task
            task.add_done_callback(
                lambda completed, task_name=name: self._on_task_done(
                    task_name, completed
                )
            )

    def _on_task_done(self, name: str, task: asyncio.Task[Any]) -> None:
        if self._stopping:
            return
        if self.fatal and task.cancelled():
            # The first failure cancels sibling tasks to stop new processing.
            return

        detail = "cancelled unexpectedly" if task.cancelled() else "stopped"
        if not task.cancelled():
            try:
                exception = task.exception()
            except asyncio.CancelledError:
                exception = None
            if exception is not None:
                detail = f"failed with {type(exception).__name__}"

        self.critical_task_failures += 1
        first_failure = self.fatal_reason is None
        if first_failure:
            self.fatal_reason = CRITICAL_TASK_REASONS[name]
            value = self._now_fn()
            self.last_failure_time = (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            )
        logger.critical(
            "Critical Cortex task %s %s; graceful process termination scheduled",
            name,
            detail,
        )

        if first_failure:
            for sibling_name, sibling in self._watched_tasks.items():
                if sibling_name != name and not sibling.done():
                    sibling.cancel()

        if first_failure and (
            self._termination_task is None or self._termination_task.done()
        ):
            self._termination_task = asyncio.create_task(
                self._terminate_after_delay()
            )

    async def _terminate_after_delay(self) -> None:
        try:
            await self._sleep_fn(self.exit_delay_seconds)
            if self._stopping or not self.fatal:
                return
            logger.critical(
                "Terminating Cortex after critical task failure: reason=%s",
                self.fatal_reason,
            )
            self._terminate_fn()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to request Cortex process termination")

    def begin_shutdown(self) -> None:
        self._stopping = True
        if self._termination_task is not None:
            self._termination_task.cancel()

    async def close(self) -> None:
        task = self._termination_task
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._termination_task = None
        self._watched_tasks = {}


def install(
    reliable: Any,
    legacy: Any,
    ledger: Any,
    *,
    supervisor: Optional[CriticalTaskSupervisor] = None,
) -> CriticalTaskSupervisor:
    """Wrap the installed Kafka lifecycle with critical-task supervision."""

    existing = getattr(reliable, "_critical_task_supervisor", None)
    if existing is not None:
        return existing

    active = supervisor or CriticalTaskSupervisor()
    reliable._critical_task_supervisor = active
    original_start = legacy.start_kafka
    original_stop = legacy.stop_kafka

    async def supervised_start() -> None:
        active.prepare_start()
        await original_start()
        try:
            active.watch(
                {
                    "kafka_consumer_task": legacy.kafka_task,
                    "dedupe_marker_follower": ledger._follower_task,
                    "dedupe_expiry_sweep": ledger._sweep_task,
                }
            )
        except Exception:
            active.begin_shutdown()
            await original_stop()
            await active.close()
            raise

    async def supervised_stop() -> None:
        active.begin_shutdown()
        try:
            await original_stop()
        finally:
            await active.close()

    reliable.reliable_start_kafka = supervised_start
    reliable.reliable_stop_kafka = supervised_stop
    legacy.start_kafka = supervised_start
    legacy.stop_kafka = supervised_stop
    return active
