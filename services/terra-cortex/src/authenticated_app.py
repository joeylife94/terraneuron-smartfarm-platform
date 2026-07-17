"""Terra-Cortex app with reliable Kafka, service auth, and event deduplication."""

import asyncio
import logging
import os

from src import main as legacy
from src.authenticated_crop_profile import get_authenticated_crop_profile_provider

logger = logging.getLogger(__name__)

# Patch the crop provider before the reliable runtime resolves application globals.
legacy.get_crop_profile_provider = get_authenticated_crop_profile_provider

from src import reliable_app as reliable  # noqa: E402
from src.kafka_event_dedup import install  # noqa: E402

install(reliable, legacy)
_dedupe_start_kafka = legacy.start_kafka


async def start_kafka_with_dedupe_retry() -> None:
    """Retry the ledger bootstrap until Kafka is ready, then start the reliable runtime."""

    max_retries = int(os.getenv("KAFKA_START_MAX_RETRIES", "10"))
    retry_delay = float(os.getenv("KAFKA_START_RETRY_SECONDS", "5"))
    for attempt in range(1, max_retries + 1):
        try:
            await _dedupe_start_kafka()
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning(
                "Kafka dedupe startup attempt %s/%s failed: %s",
                attempt,
                max_retries,
                exc,
            )
            if attempt == max_retries:
                raise
            await asyncio.sleep(retry_delay)


legacy.start_kafka = start_kafka_with_dedupe_retry
app = reliable.app
