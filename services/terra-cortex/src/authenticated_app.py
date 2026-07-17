"""Terra-Cortex application with reliable Kafka, service auth, and event deduplication."""

from src import main as legacy
from src.authenticated_crop_profile import get_authenticated_crop_profile_provider

# Patch the crop provider before the reliable runtime resolves application globals.
legacy.get_crop_profile_provider = get_authenticated_crop_profile_provider

from src import reliable_app as reliable  # noqa: E402
from src.kafka_event_dedup import install  # noqa: E402

install(reliable, legacy)
app = reliable.app
