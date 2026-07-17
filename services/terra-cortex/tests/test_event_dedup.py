import asyncio
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from aiokafka.structs import TopicPartition

from src import kafka_event_dedup as dedup
from src.event_identity import derive_event_id, measurement_fingerprint


class FrozenClock:
    def __init__(self, value):
        self.value = value

    def now(self):
        return self.value

    def advance(self, **kwargs):
        self.value += timedelta(**kwargs)


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
    def __init__(self, markers):
        self.markers = list(markers)
        self.assigned = []
        self.stopped = False
        self.delivered = False

    async def start(self):
        return None

    def partitions_for_topic(self, _topic):
        return {0}

    def assign(self, partitions):
        self.assigned = partitions

    def assignment(self):
        return set(self.assigned)

    async def seek_to_beginning(self, *_partitions):
        return None

    async def end_offsets(self, partitions):
        return {partition: len(self.markers) for partition in partitions}

    async def getmany(self, *_partitions, timeout_ms=None, max_records=None):
        if self.delivered:
            return {}
        self.delivered = True
        partition = self.assigned[0]
        messages = [
            SimpleNamespace(
                value=marker,
                key=(marker.get("event_id") or "").encode("utf-8"),
                timestamp=None,
            )
            for marker in self.markers
        ]
        return {partition: messages}

    async def position(self, _partition):
        return len(self.markers) if self.delivered else 0

    async def stop(self):
        self.stopped = True


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def register(fn):
            self.routes[path] = fn
            return fn

        return register


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


def marker(event_id, fingerprint, processed_at, expires_at, status="PROCESSED"):
    return {
        "event_id": event_id,
        "fingerprint": fingerprint,
        "processed_at": processed_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "status": status,
    }


def fake_runtime():
    async def start():
        return None

    async def stop():
        return None

    async def original_process(*_args, **_kwargs):
        return None

    async def analyze(*_args, **_kwargs):
        return None

    async def accumulate(*_args, **_kwargs):
        return None

    async def consume():
        return None

    reliable = SimpleNamespace(
        reliable_start_kafka=start,
        reliable_stop_kafka=stop,
        _process_message=original_process,
        _analyze_sensor_event=analyze,
        _accumulate_knowledge_best_effort=accumulate,
        reliable_consume_messages=consume,
        MAX_PROCESSING_ATTEMPTS=3,
        BASE_RETRY_SECONDS=1,
        DLT_TOPIC="raw-sensor-data.DLT",
        CONSUMER_REBALANCE_LISTENER=None,
        app=FakeApp(),
        generate_trace_id=lambda: "generated-trace",
        _trace_id_from_headers=lambda _message: "trace-1",
        _source_position=lambda message: f"{message.topic}:{message.partition}:{message.offset}",
        _retry_delay=lambda attempt: attempt,
        _delivery_stats={
            "processed": 0,
            "retried": 0,
            "dead_lettered": 0,
            "transaction_failures": 0,
        },
    )
    legacy = SimpleNamespace(
        KAFKA_BOOTSTRAP_SERVERS="kafka:9092",
        OUTPUT_TOPIC="processed-insights",
        ACTION_PLAN_TOPIC="action-plans",
        CONSUMER_GROUP="terra-cortex-group",
        producer=None,
    )
    return reliable, legacy


def test_event_identity_matches_java_contract():
    assert derive_event_id(sensor_payload()) == (
        "evt-88ea9753f06c5b9e2f54fd4869938235134c892d56f90c0e038ee64281890fd1"
    )


def test_same_event_is_suppressed_within_processing_time_window():
    clock = FrozenClock(datetime(2026, 7, 17, tzinfo=timezone.utc))
    ledger = dedup.KafkaEventLedger(
        "dedupe-topic", retention_days=30, now_fn=clock.now
    )
    event_id = "provider:event-42"
    fingerprint = measurement_fingerprint(sensor_payload(event_id))

    ledger.mark_local(event_id, fingerprint)
    clock.advance(days=29)

    assert ledger.classify(event_id, fingerprint) == dedup.EventClassification.DUPLICATE


def test_expired_event_is_processed_as_new():
    clock = FrozenClock(datetime(2026, 7, 17, tzinfo=timezone.utc))
    ledger = dedup.KafkaEventLedger(
        "dedupe-topic", retention_days=30, now_fn=clock.now
    )
    event_id = "provider:event-42"
    fingerprint = measurement_fingerprint(sensor_payload(event_id))

    ledger.mark_local(event_id, fingerprint)
    clock.advance(days=30)

    assert ledger.classify(event_id, fingerprint) == dedup.EventClassification.NEW
    assert ledger.size == 0


def test_id_conflict_is_detected_only_within_retention_window():
    clock = FrozenClock(datetime(2026, 7, 17, tzinfo=timezone.utc))
    ledger = dedup.KafkaEventLedger(
        "dedupe-topic", retention_days=30, now_fn=clock.now
    )
    event_id = "provider:event-42"
    original = measurement_fingerprint(sensor_payload(event_id))
    changed = measurement_fingerprint(sensor_payload(event_id, value=32.0))

    ledger.mark_local(event_id, original)
    assert ledger.classify(event_id, changed) == dedup.EventClassification.CONFLICT

    clock.advance(days=30)
    assert ledger.classify(event_id, changed) == dedup.EventClassification.NEW


def test_sweep_removes_only_expired_markers():
    clock = FrozenClock(datetime(2026, 7, 17, tzinfo=timezone.utc))
    ledger = dedup.KafkaEventLedger(
        "dedupe-topic", retention_days=30, now_fn=clock.now
    )
    old_fingerprint = measurement_fingerprint(sensor_payload("old"))
    new_fingerprint = measurement_fingerprint(sensor_payload("new", value=32.0))
    ledger.mark_local("old", old_fingerprint)
    clock.advance(days=31)
    ledger.mark_local("new", new_fingerprint)

    assert ledger.sweep_expired() == 1
    assert ledger.classify("old", old_fingerprint) == dedup.EventClassification.NEW
    assert ledger.classify("new", new_fingerprint) == dedup.EventClassification.DUPLICATE
    assert ledger.expired_markers_swept == 1


def test_restore_skips_expired_markers_and_reports_statistics(monkeypatch):
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    clock = FrozenClock(now)
    active = marker("active", "fp-active", now - timedelta(days=1), now + timedelta(days=29))
    expired = marker("expired", "fp-expired", now - timedelta(days=31), now - timedelta(days=1))
    fake_consumer = FakeRestoreConsumer([active, expired])
    monkeypatch.setattr(dedup, "AIOKafkaConsumer", lambda **_kwargs: fake_consumer)

    ledger = dedup.KafkaEventLedger(
        "dedupe-topic", retention_days=30, now_fn=clock.now
    )
    asyncio.run(ledger.restore("kafka:9092"))

    assert ledger.restore_records_scanned == 2
    assert ledger.expired_markers_skipped == 1
    assert ledger.active_event_ids_loaded == 1
    assert ledger.last_restore_duration_ms >= 0
    assert ledger.classify("active", "fp-active") == dedup.EventClassification.DUPLICATE
    assert ledger.classify("expired", "fp-expired") == dedup.EventClassification.NEW
    assert fake_consumer.stopped is True


def test_legacy_marker_derives_expiry_from_processed_at(monkeypatch):
    now = datetime(2026, 7, 17, tzinfo=timezone.utc)
    legacy_marker = {
        "event_id": "legacy",
        "fingerprint": "fp-legacy",
        "processed_at": (now - timedelta(days=5)).isoformat(),
        "outcome": "PROCESSED",
    }
    fake_consumer = FakeRestoreConsumer([legacy_marker])
    monkeypatch.setattr(dedup, "AIOKafkaConsumer", lambda **_kwargs: fake_consumer)
    ledger = dedup.KafkaEventLedger(
        "dedupe-topic", retention_days=30, now_fn=lambda: now
    )

    asyncio.run(ledger.restore("kafka:9092"))

    assert ledger.classify("legacy", "fp-legacy") == dedup.EventClassification.DUPLICATE


def test_topic_configuration_is_created_and_enforced(monkeypatch):
    instances = []

    class FakeAdmin:
        def __init__(self, **_kwargs):
            self.created = []
            self.altered = []
            self.closed = False
            instances.append(self)

        async def start(self):
            return None

        async def create_topics(self, topics):
            self.created.extend(topics)

        async def alter_configs(self, resources):
            self.altered.extend(resources)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(dedup, "AIOKafkaAdminClient", FakeAdmin)
    ledger = dedup.KafkaEventLedger("dedupe-topic", retention_days=30)

    asyncio.run(ledger.ensure_topic("kafka:9092"))

    admin = instances[0]
    assert admin.created[0].topic_configs == ledger.topic_configs
    assert admin.altered[0].configs == ledger.topic_configs
    assert ledger.topic_configs == {
        "cleanup.policy": "compact,delete",
        "retention.ms": "2592000000",
        "delete.retention.ms": "86400000",
        "segment.ms": "3600000",
        "min.cleanable.dirty.ratio": "0.1",
    }
    assert admin.closed is True


def test_outputs_marker_and_offset_share_one_transaction():
    clock = FrozenClock(datetime(2026, 7, 17, tzinfo=timezone.utc))
    producer = FakeProducer()
    ledger = dedup.KafkaEventLedger("dedupe-topic", now_fn=clock.now)
    message = source_message()
    payload = sensor_payload()
    event_id = derive_event_id(payload)
    fingerprint = measurement_fingerprint(payload)
    marker_value = ledger.build_marker(event_id, fingerprint, message, "PROCESSED")
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
            marker_value,
        )
    )

    assert producer.transaction_count == 1
    assert [record["topic"] for record in producer.sent] == [
        "processed-insights",
        "action-plans",
        "dedupe-topic",
    ]
    stored_marker = producer.sent[-1]
    assert stored_marker["key"] == event_id.encode("utf-8")
    assert stored_marker["value"]["event_id"] == event_id
    assert stored_marker["value"]["fingerprint"] == fingerprint
    assert stored_marker["value"]["status"] == "PROCESSED"
    assert stored_marker["value"]["processed_at"] == "2026-07-17T00:00:00+00:00"
    assert stored_marker["value"]["expires_at"] == "2026-08-16T00:00:00+00:00"
    offsets, group_id = producer.offset_commits[0]
    assert offsets[next(iter(offsets))] == 42
    assert group_id == "terra-cortex-group"


def test_invalid_identity_payload_is_dead_lettered_with_marker_and_offset():
    reliable, legacy = fake_runtime()
    producer = FakeProducer()
    dedup.install(reliable, legacy)
    invalid = sensor_payload("provider:invalid", value="not-a-number")

    asyncio.run(
        reliable._process_message(
            source_message(invalid),
            producer=producer,
            sleep_fn=asyncio.sleep,
        )
    )

    assert producer.transaction_count == 1
    assert [record["topic"] for record in producer.sent] == [
        "raw-sensor-data.DLT",
        "cortex-processed-event-ids",
    ]
    assert producer.sent[1]["value"]["status"] == "DEAD_LETTERED"
    assert producer.sent[1]["value"]["event_id"] == "provider:invalid"
    assert len(producer.offset_commits) == 1
    assert reliable._delivery_stats["dead_lettered"] == 1


def test_id_conflict_within_retention_is_dead_lettered_without_replacing_marker():
    reliable, legacy = fake_runtime()
    producer = FakeProducer()
    ledger = dedup.install(reliable, legacy)
    event_id = "provider:event-42"
    original = sensor_payload(event_id, value=31.5)
    changed = sensor_payload(event_id, value=32.0)
    original_fingerprint = measurement_fingerprint(original)
    ledger.mark_local(event_id, original_fingerprint)

    asyncio.run(
        reliable._process_message(
            source_message(changed),
            producer=producer,
            sleep_fn=asyncio.sleep,
        )
    )

    assert producer.transaction_count == 1
    assert [record["topic"] for record in producer.sent] == [
        "raw-sensor-data.DLT"
    ]
    assert producer.sent[0]["value"]["data"]["error_code"] == "EVENT_ID_CONFLICT"
    assert len(producer.offset_commits) == 1
    assert reliable._delivery_stats["event_id_conflicts"] == 1
    assert ledger.classify(event_id, original_fingerprint) == (
        dedup.EventClassification.DUPLICATE
    )


def test_duplicate_offset_commit_has_no_output_records():
    producer = FakeProducer()
    message = source_message()

    asyncio.run(dedup._commit_duplicate(producer, message, "terra-cortex-group"))

    assert producer.transaction_count == 1
    assert producer.sent == []
    offsets, group_id = producer.offset_commits[0]
    assert offsets[TopicPartition("raw-sensor-data", 2)] == 42
    assert group_id == "terra-cortex-group"


def test_rebalance_listener_catches_up_marker_changelog():
    calls = []

    class FakeLedger:
        async def catch_up(self):
            calls.append("caught-up")

    listener = dedup.LedgerRebalanceListener(FakeLedger())
    asyncio.run(listener.on_partitions_assigned({TopicPartition("raw", 0)}))

    assert calls == ["caught-up"]


def test_operations_status_exposes_retention_restore_sweep_and_policy():
    clock = FrozenClock(datetime(2026, 7, 17, tzinfo=timezone.utc))
    ledger = dedup.KafkaEventLedger(
        "dedupe-topic",
        retention_days=30,
        sweep_interval_seconds=300,
        now_fn=clock.now,
    )
    ledger.restore_records_scanned = 12
    ledger.expired_markers_skipped = 2
    ledger.active_event_ids_loaded = 10
    ledger.last_restore_duration_ms = 47
    ledger.next_scheduled_sweep = clock.now() + timedelta(seconds=300)
    stats = {
        "duplicates_suppressed": 3,
        "event_id_conflicts": 1,
        "legacy_event_ids_generated": 4,
    }

    payload = dedup._status_payload(ledger, stats)

    assert payload["configured_retention"] == {
        "days": 30,
        "milliseconds": 2592000000,
        "basis": "cortex_processed_at",
    }
    assert payload["active_marker_count"] == 0
    assert payload["restore"]["restore_records_scanned"] == 12
    assert payload["restore"]["restore_duration_ms"] == 47
    assert payload["topic_policy"]["cleanup.policy"] == "compact,delete"
    assert payload["sweep_interval_seconds"] == 300
    assert payload["next_scheduled_sweep"] == "2026-07-17T00:05:00+00:00"
    assert "event_ids" not in payload
