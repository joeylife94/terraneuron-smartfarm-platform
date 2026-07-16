import asyncio

import jwt

from src.authenticated_crop_profile import AuthenticatedCropProfileProvider
from src.service_auth import ServiceAuthConfig, ServiceTokenProvider


TEST_SECRET = "TEST_ONLY_CHANGE_ME_SERVICE_JWT_SECRET_32_CHARS"


def config(**overrides):
    values = {
        "secret": TEST_SECRET,
        "issuer": "terraneuron-internal",
        "audience": "terra-ops",
        "subject": "terra-cortex",
        "scope": "crop:read",
        "ttl_seconds": 60,
        "refresh_skew_seconds": 10,
    }
    values.update(overrides)
    return ServiceAuthConfig(**values)


def test_service_token_has_short_lived_scoped_claims():
    provider = ServiceTokenProvider(config())

    token = provider.get_token(now=1_000)
    claims = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=["HS256"],
        audience="terra-ops",
        issuer="terraneuron-internal",
        options={"verify_iat": False, "verify_nbf": False, "verify_exp": False},
    )

    assert claims["sub"] == "terra-cortex"
    assert claims["type"] == "service"
    assert claims["scope"] == "crop:read"
    assert claims["exp"] - claims["iat"] == 60
    assert claims["jti"]


def test_service_token_is_cached_then_rotated_before_expiry():
    provider = ServiceTokenProvider(config())

    first = provider.get_token(now=1_000)
    cached = provider.get_token(now=1_020)
    rotated = provider.get_token(now=1_051)

    assert first == cached
    assert rotated != first
    assert provider.issued_count == 2


def test_crop_profile_request_sends_bearer_service_token(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"hasCropProfile": False, "message": "none"}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers):
            captured["url"] = url
            captured["headers"] = headers
            return FakeResponse()

    monkeypatch.setattr("src.authenticated_crop_profile.httpx.AsyncClient", FakeClient)
    token_provider = ServiceTokenProvider(config())
    provider = AuthenticatedCropProfileProvider(token_provider=token_provider)
    provider.base_url = "http://terra-ops:8080"

    context = asyncio.run(provider.get_crop_context("farm-A"))

    assert context is not None
    assert context.has_crop_profile is False
    assert captured["url"].endswith("/api/farms/farm-A/optimal-conditions")
    assert captured["headers"]["Authorization"].startswith("Bearer ")

    token = captured["headers"]["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(
        token,
        TEST_SECRET,
        algorithms=["HS256"],
        audience="terra-ops",
        issuer="terraneuron-internal",
    )
    assert claims["scope"] == "crop:read"


def test_service_auth_stats_never_expose_secret():
    provider = ServiceTokenProvider(config())
    stats = provider.get_stats()

    assert "secret" not in stats
    assert TEST_SECRET not in str(stats)
