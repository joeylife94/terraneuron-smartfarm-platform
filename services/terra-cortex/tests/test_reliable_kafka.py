import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone
from types import SimpleNamespace

from src import reliable_app as runtime
from src.models import Insight, SensorData


class FakeTransaction(AbstractAsyncContextManager):
    def __init__(self, producer):
        self.producer = producer

    async def __aenter__(self):
        self.producer.transaction_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeProducer:
    def __init__(self, fail_sends=0):
        self.fail_sends = fail_sends
        self.transaction_count = 0
        self.sent = []
        self.offset_commits = []

    def transaction(self):
        return FakeTransaction(self)

    async def send_and_wait(self, topic, value, key=None, headers=None):
        if self.fail_sends > 0:
            self.fail_sends -= 1
            raise RuntimeError("broker unavailable")
        self.sent.append(
            {
                "topic": topic,
                "value": value,
                "key": key,
                "headers": headers,
            }
        )

    async def send_offsets_to_transaction(self, offsets, group_id):
        self.offset_commits.append((offsets, group_id))


def message(value=None):
    return SimpleNamespace(
        topic="raw-sensor-data",
        partition=2,
        offset=41,
        value=value
        or {
            "farmId": "farm-1",
            "sensorType": "temperature",
            "value": 31.5,
            "timestamp": "2026-07-16T00:00:00Z",
        },
        key=b"sensor-1",
        headers=[("trace_id", b"trace-input-1")],
    )


def result(with_action_plan=True):
    sensor = SensorData(
        farmId="farm-1",
        sensorType="temperature",
        value=31.5,
        timestamp=datetime(2026, 7, 16, tzinfo=timezone.utc),
    )
    insight = Insight(
        farmId="farm-1",
        sensorType="temperature",
        status="ANOMALY",
        severity="warning",
        message="high temperature",
        confidence=0.95,
        detectedAt=datetime(2026, 7, 16, tzinfo=timezone.utc),
        rawValue=31.5,
    )
    return runtime.AnalysisResult(
        trace_id="trace-input-1",
        sensor_data=sensor,
        insight=insight,
        insight_event={"type": "insight", "data": {"trace_id": "trace-input-1"}},
        action_plan_event=(
            {"type": "action-plan", "data": {"trace_id": "trace-input-1"}}
            if with_action_plan
            else None
        ),
    )


def test_outputs_and_input_offset_commit_in_one_transaction():
    producer = FakeProducer()

    asyncio.run(
        runtime._publish_result_transactionally(
            producer,
            message(),
            result(with_action_plan=True),
        )
    )

    assert producer.transaction_count == 1
    assert [item["topic"] for item in producer.sent] == [
        runtime.legacy.OUTPUT_TOPIC,
        runtime.legacy.ACTION_PLAN_TOPIC,
    ]
    assert len(producer.offset_commits) == 1
    offsets, group_id = producer.offset_commits[0]
    topic_partition = next(iter(offsets))
    assert topic_partition.topic == "raw-sensor-data"
    assert topic_partition.partition == 2
    assert offsets[topic_partition] == 42
    assert group_id == runtime.legacy.CONSUMER_GROUP


def test_publish_retry_reuses_completed_analysis():
    producer = FakeProducer(fail_sends=1)
    analyze_calls = 0
    sleeps = []

    async def analyze(payload, trace_id):
        nonlocal analyze_calls
        analyze_calls += 1
        return result(with_action_plan=False)

    async def sleep(delay):
        sleeps.append(delay)

    asyncio.run(
        runtime._process_message(
            message(),
            producer=producer,
            analyze_fn=analyze,
            sleep_fn=sleep,
            max_attempts=2,
        )
    )

    assert analyze_calls == 1
    assert producer.transaction_count == 2
    assert sleeps == [runtime.BASE_RETRY_SECONDS]
    assert [item["topic"] for item in producer.sent] == [
        runtime.legacy.OUTPUT_TOPIC
    ]
    assert len(producer.offset_commits) == 1


def test_exhausted_record_is_dead_lettered_with_offset_commit():
    producer = FakeProducer()
    analyze_calls = 0

    async def analyze(payload, trace_id):
        nonlocal analyze_calls
        analyze_calls += 1
        raise ValueError("invalid sensor payload")

    async def sleep(_delay):
        return None

    asyncio.run(
        runtime._process_message(
            message({"unexpected": "payload"}),
            producer=producer,
            analyze_fn=analyze,
            sleep_fn=sleep,
            max_attempts=2,
        )
    )

    assert analyze_calls == 2
    assert producer.transaction_count == 1
    assert len(producer.sent) == 1
    dlt = producer.sent[0]
    assert dlt["topic"] == runtime.DLT_TOPIC
    assert dlt["value"]["data"]["source_offset"] == 41
    assert dlt["value"]["data"]["attempts"] == 2
    assert dlt["value"]["data"]["error_type"] == "ValueError"
    assert len(producer.offset_commits) == 1


def test_trace_id_is_preserved_from_input_headers():
    assert runtime._trace_id_from_headers(message()) == "trace-input-1"
