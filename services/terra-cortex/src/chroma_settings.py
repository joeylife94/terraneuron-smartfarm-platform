"""Shared chromadb client settings for every embedded Chroma store.

chromadb 0.4.22 enables anonymized PostHog telemetry by default. Every
``Chroma(...)`` site in terra-cortex passes the settings built here, so
telemetry is always off, whatever ``ANONYMIZED_TELEMETRY`` or a ``.env`` file
says.

The settings have to be identical at every site. chromadb caches one client
system per ``persist_directory``. If ``RAGAdvisor`` and ``KnowledgeCollector``
open the same store in one process with different settings, chromadb raises
"An instance of Chroma already exists ... with different settings".

chromadb is imported lazily. A broken chromadb install then disables RAG at
the call sites, which already catch that, instead of breaking module import.
"""
import logging

# Even with telemetry disabled, chromadb 0.4.22 still calls
# ``posthog.capture(user_id, event, properties)`` and only sets
# ``posthog.disabled``. posthog>=6 changed ``capture()``, so every call raises
# TypeError, which chromadb catches and logs at ERROR as "Failed to send
# telemetry event ...". Nothing is sent. The logger is quieted here rather
# than by pinning posthog<6, because that pin would make chromadb's default-on
# telemetry reach PostHog for any client created without these settings.
CHROMA_TELEMETRY_LOGGER = "chromadb.telemetry.product.posthog"
logging.getLogger(CHROMA_TELEMETRY_LOGGER).setLevel(logging.CRITICAL)


def chroma_client_settings(persist_directory: str):
    """Return fresh persistent chromadb settings with telemetry disabled.

    A new object is returned on each call because LangChain's ``Chroma``
    writes ``persist_directory`` back onto the settings it is given.
    """
    import chromadb.config

    return chromadb.config.Settings(
        anonymized_telemetry=False,
        is_persistent=True,
        persist_directory=str(persist_directory),
    )
