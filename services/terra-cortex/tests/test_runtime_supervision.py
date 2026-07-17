import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from src import runtime_supervision as supervision


async def settle_callbacks():
    for _ in range(4):
        await asyncio.sleep(0)


def test_unexpected_task_completion_marks_fatal_and_requests_termination():
    async def scenario():
        terminations = []
        supervisor = supervision.CriticalTaskSupervisor(
            exit_delay_seconds=0,
            terminate_fn=lambda: terminations.append("terminated"),
            now_fn=lambda: datetime(2026, 7, 17, tzinfo=timezone.utc),
        )
        supervisor.prepare_start()
        task = asyncio.create_task(asyncio.sleep(0))
        supervisor.watch({"kafka_consumer_task": task})

        await task
        await settle_callbacks()

        assert supervisor.fatal is True
        assert supervisor.fatal_reason == "KAFKA_CONSUMER_TASK_STOPPED"
        assert supervisor.critical_task_failures == 1
        assert supervisor.last_failure_time.isoformat() == (
            "2026-07-17T00:00:00+00:00"
        )
        assert terminations == ["terminated"]
        await supervisor.close()

    asyncio.run(scenario())


def test_task_exception_uses_safe_reason_code_only():
    async def fail():
        raise RuntimeError("broker address and sensitive runtime detail")

    async def scenario():
        supervisor = supervision.CriticalTaskSupervisor(
            exit_delay_seconds=0,
            terminate_fn=lambda: None,
        )
        supervisor.prepare_start()
        task = asyncio.create_task(fail())
        supervisor.watch({"dedupe_marker_follower": task})

        await settle_callbacks()

        assert supervisor.fatal_reason == "DEDUPE_MARKER_FOLLOWER_STOPPED"
        assert "broker" not in supervisor.fatal_reason
        assert supervisor.critical_task_failures == 1
        await supervisor.close()

    asyncio.run(scenario())


def test_unexpected_cancellation_is_fatal():
    async def scenario():
        terminations = []
        supervisor = supervision.CriticalTaskSupervisor(
            exit_delay_seconds=0,
            terminate_fn=lambda: terminations.append("terminated"),
        )
        supervisor.prepare_start()
        task = asyncio.create_task(asyncio.sleep(60))
        supervisor.watch({"dedupe_expiry_sweep": task})

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await settle_callbacks()

        assert supervisor.fatal_reason == "DEDUPE_EXPIRY_SWEEP_STOPPED"
        assert terminations == ["terminated"]
        await supervisor.close()

    asyncio.run(scenario())


def test_first_failure_cancels_siblings_before_exit_delay():
    async def scenario():
        release = asyncio.Event()

        async def wait_for_release(_delay):
            await release.wait()

        supervisor = supervision.CriticalTaskSupervisor(
            exit_delay_seconds=5,
            terminate_fn=lambda: None,
            sleep_fn=wait_for_release,
        )
        supervisor.prepare_start()
        failed = asyncio.create_task(asyncio.sleep(0))
        consumer = asyncio.create_task(asyncio.sleep(60))
        sweep = asyncio.create_task(asyncio.sleep(60))
        supervisor.watch(
            {
                "dedupe_marker_follower": failed,
                "kafka_consumer_task": consumer,
                "dedupe_expiry_sweep": sweep,
            }
        )

        await failed
        await settle_callbacks()

        assert consumer.cancelled() is True
        assert sweep.cancelled() is True
        assert supervisor.critical_task_failures == 1
        assert supervisor.termination_scheduled is True
        supervisor.begin_shutdown()
        await supervisor.close()

    asyncio.run(scenario())


def test_normal_shutdown_cancellation_is_not_counted_as_failure():
    async def scenario():
        terminations = []
        supervisor = supervision.CriticalTaskSupervisor(
            exit_delay_seconds=0,
            terminate_fn=lambda: terminations.append("terminated"),
        )
        supervisor.prepare_start()
        task = asyncio.create_task(asyncio.sleep(60))
        supervisor.watch({"kafka_consumer_task": task})

        supervisor.begin_shutdown()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await settle_callbacks()

        assert supervisor.fatal is False
        assert supervisor.critical_task_failures == 0
        assert terminations == []
        await supervisor.close()

    asyncio.run(scenario())


def test_shutdown_cancels_delayed_termination():
    async def scenario():
        release = asyncio.Event()
        terminations = []

        async def wait_for_release(_delay):
            await release.wait()

        supervisor = supervision.CriticalTaskSupervisor(
            exit_delay_seconds=5,
            terminate_fn=lambda: terminations.append("terminated"),
            sleep_fn=wait_for_release,
        )
        supervisor.prepare_start()
        task = asyncio.create_task(asyncio.sleep(0))
        supervisor.watch({"kafka_consumer_task": task})
        await task
        await asyncio.sleep(0)

        assert supervisor.termination_scheduled is True
        supervisor.begin_shutdown()
        await supervisor.close()
        release.set()

        assert terminations == []

    asyncio.run(scenario())


def test_lifecycle_wrapper_watches_tasks_and_ignores_orderly_stop():
    async def scenario():
        calls = []
        legacy = SimpleNamespace(kafka_task=None)
        ledger = SimpleNamespace(_follower_task=None, _sweep_task=None)

        async def wait_forever():
            await asyncio.Event().wait()

        async def start():
            calls.append("start")
            legacy.kafka_task = asyncio.create_task(wait_forever())
            ledger._follower_task = asyncio.create_task(wait_forever())
            ledger._sweep_task = asyncio.create_task(wait_forever())

        async def stop():
            calls.append("stop")
            tasks = [
                legacy.kafka_task,
                ledger._follower_task,
                ledger._sweep_task,
            ]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        legacy.start_kafka = start
        legacy.stop_kafka = stop
        reliable = SimpleNamespace(
            reliable_start_kafka=start,
            reliable_stop_kafka=stop,
        )
        supervisor = supervision.CriticalTaskSupervisor(
            terminate_fn=lambda: None
        )

        installed = supervision.install(
            reliable, legacy, ledger, supervisor=supervisor
        )
        assert supervision.install(reliable, legacy, ledger) is installed
        await legacy.start_kafka()
        assert set(supervisor._watched_tasks) == {
            "kafka_consumer_task",
            "dedupe_marker_follower",
            "dedupe_expiry_sweep",
        }
        await legacy.stop_kafka()

        assert calls == ["start", "stop"]
        assert supervisor.critical_task_failures == 0

    asyncio.run(scenario())


def test_missing_critical_task_aborts_started_runtime():
    async def scenario():
        calls = []

        async def start():
            calls.append("start")

        async def stop():
            calls.append("stop")

        legacy = SimpleNamespace(
            start_kafka=start,
            stop_kafka=stop,
            kafka_task=None,
        )
        ledger = SimpleNamespace(_follower_task=None, _sweep_task=None)
        reliable = SimpleNamespace(
            reliable_start_kafka=start,
            reliable_stop_kafka=stop,
        )
        supervision.install(reliable, legacy, ledger)

        with pytest.raises(RuntimeError, match="critical runtime tasks"):
            await legacy.start_kafka()

        assert calls == ["start", "stop"]

    asyncio.run(scenario())


def test_negative_exit_delay_is_rejected():
    with pytest.raises(ValueError, match="must not be negative"):
        supervision.CriticalTaskSupervisor(exit_delay_seconds=-1)
