"""Terra-Cortex application with reliable Kafka and scoped Terra-Ops authentication."""

from src import main as legacy
from src.authenticated_crop_profile import get_authenticated_crop_profile_provider

# The original lifespan resolves this module global when startup begins. Patch it before importing
# the reliable Kafka wrapper so the existing API surface and lifecycle remain otherwise unchanged.
legacy.get_crop_profile_provider = get_authenticated_crop_profile_provider

from src.reliable_app import app  # noqa: E402,F401
