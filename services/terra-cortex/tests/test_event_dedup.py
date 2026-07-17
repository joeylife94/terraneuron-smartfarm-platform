import asyncio
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace

from aiokafka.structs import TopicPartition

from src import kafka_event_dedup as dedup
from src.event_identity import derive_event_id, measurement_fingerprint


class FakeTransaction(AbstractAsyncContextManager):
    def __init__(self, producer):
        self.producer = producer

    async def __aenter__(self):
        self.producer.transaction_count += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeProducer:
    def __init__(self):
        self.transaction_count = 0
        self.sent = []
        self.offset_commits = []

    def transaction(self):
        return FakeTransaction(self)

    async def send_and_wait(self, topic, value, key=None, headers=None):
        self.sent.append(
            {"topic": topic, "value": value, "key": key, "headers": headers}
        )

    async def send_offsets_to_transaction(self, offsets, group_id):
        self.offset_commits.append((offsets, group_id))


class FakeRestoreConsumer:
    def __init__(self, marker):
        self.marker = marker
        self.assigned = []
        self.stopped = False

    async def start(self):
        return None

    def partitions_for_topic(self, _topic):
        return {0}

    def assign(self, partitions):
        self.assigned = partitions

    async def seek_to_beginning(self, *_partitions):
        return None

    async def end_offsets(self, partitions):
        return {partition: 1 for partition in partitions}

    async def getmany(self, *_partitions, timeout_ms=None, max_records=None):
        partition = self.assigned[0]
        return {partition: [SimpleNamespace(value=self.marker)]}

    async def position(self, _partition):
        return 1

    async def stop(self):
        self.stopped = True


def sensor_payload(event_id=None, value=31.5):
    payload = {
        "farmId": "farm-1",
        "sensorId": "sensor-1",
        "sensorType": "temperature",
        "value": value,
        "unit": "°C",
        "timestamp": "2026-07-16T00:00:00Z",
    }
    if event_id:
        payload["eventId"] = event_id
    return payload


def source_message(payload=None):
    return SimpleNamespace(
        topic="raw-sensor-data",
        partition=2,
        offset=41,
        value=payload or sensor_payload(),
        key=b"event-key",
        headers=[("trace_id", b"trace-1")],
    )


def test_event_identity_matches_java_contract():
    assert derive_event_id(sensor_payload()) == (
        "evt-88ea9753f06c5b9e2f54fd4869938235134c892d56f90c0e038ee64281890fd1"
    )


def test_ledger_distinguishes_duplicate_from_conflicting_payload():
    ledger = dedup.KafkaEventLedger("dedupe-topic")
    event_id = "provider:event-42"
    original = measurement_fingerprint(sensor_payload(event_id))
    changed = measurement_fingerprint(sensor_payload(event_id, value=32.0))

    assert ledger.classify(event_id, original) == dedup.EventClassification.NEW
    ledger.mark_local(event_id, original)
    assert ledger.classify(event_id, original) == dedup.EventClassification.DUPLICATE
    assert ledger.classify(event_id, changed) == dedup.EventClassification.CONFLICT


def test_outputs_marker_and_offset_share_one_transaction():
    producer = FakeProducer()
    ledger = dedup.KafkaEventLedger("dedupe-topic")
    message = source_message()
    payload = sensor_payload()
    event_id = derive_event_id(payload)
    fingerprint = measurement_fingerprint(payload)
    reliable = SimpleNamespace()
    legacy = SimpleNamespace(
        OUTPUT_TOPIC="processed-insights",
        ACTION_PLAN_TOPIC="action-plans",
        CONSUMER_GROUP="terra-cortex-group",
    )
    result = SimpleNamespace(
        trace_id="trace-1",
        sensor_data=SimpleNamespace(farmId="farm-1"),
        insight_event={"type": "insight"},
        action_plan_event={"type": "plan"},
    )

    asyncio.run(
        dedup._publish_result_with_marker(
            reliable,
            legacy,
            ledger,
            producer,
            message,
            result,
            event_id,
            fingerprint,
        )
    )

    assert producer.transaction_count == 1
    assert [record["topic"] for record in producer.sent] == [
        "processed-insights",
        "action-plans",
        "dedupe-topic",
    ]
    marker = producer.sent[-1]
    assert marker["key"] == event_id.encode("utf-8")
    assert marker["value"]["event_id"] == event_id
    assert marker["value"]["fingerprint"] == fingerprint
    assert len(producer.offset_commits) == 1
    offsets, group_id = producer.offset_commits[0]
    partition = next(iter(offsets))
    assert offsets[partition] == 42
    assert group_id == "terra-cortex-group"


def test_restart_restore_suppresses_previously_committed_event(monkeypatch):
    payload = sensor_payload()
    event_id = derive_event_id(payload)
    fingerprint = measurement_fingerprint(payload)
    marker = {
        "event_id": event_id,
        "fingerprint": fingerprint,
        "outcome": "PROCESSED",
    }
    fake_consumer = FakeRestoreConsumer(marker)
    monkeypatch.setattr(dedup, "AIOKafkaConsumer", lambda **_kwargs: fake_consumer)

    restarted_ledger = dedup.KafkaEventLedger("dedupe-topic")
    asyncio.run(restarted_ledger.restore("kafka:9092"))

    assert restarted_ledger.restored_markers == 1
    assert restarted_ledger.classify(event_id, fingerprint) == (
        dedup.EventClassification.DUPLICATE
    )
    assert fake_consumer.stopped is True


def test_duplicate_offset_commit_has_no_output_records():
    producer = FakeProducer()
    message = source_message()

    asyncio.run(
        dedup._commit_duplicate(producer, message, "terra-cortex-group")
    )

    assert producer.transaction_count == 1
    assert producer.sent == []
    offsets, group_id = producer.offset_commits[0]
    assert offsets[TopicPartition("raw-sensor-data", 2)] == 42
    assert group_id == "terra-cortex-group"
