import asyncio
import json

import jwt
import pytest

from src.authenticated_crop_profile import AuthenticatedCropProfileProvider
from src.service_auth import ServiceAuthConfig, ServiceTokenProvider


TEST_SECRET = "TEST_ONLY_CHANGE_ME_SERVICE_JWT_SECRET_32_CHARS"
NO_TIME_CHECKS = {"verify_iat": False, "verify_nbf": False, "verify_exp": False}
# Throwaway P-256 public key: public-key material must never be usable as an HMAC secret.
TEST_ONLY_PUBLIC_KEY_PEM = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEEVs/o5+uQbTjL3chynL4wXgUg2R9\n"
    "q9UU8I5mEovUf86QZ7kOBIjJwqnzD1omageEHWwHdBO6B+dFabmdT9POxg==\n"
    "-----END PUBLIC KEY-----\n"
)


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


def _decode(token, secret=TEST_SECRET, **kwargs):
    params = {
        "algorithms": ["HS256"],
        "audience": "terra-ops",
        "issuer": "terraneuron-internal",
        "options": NO_TIME_CHECKS,
    }
    params.update(kwargs)
    return jwt.decode(token, secret, **params)


def _unverified_claims(token):
    return jwt.decode(token, options={"verify_signature": False})


def test_service_token_header_is_pinned_to_hs256():
    token = ServiceTokenProvider(config()).get_token(now=1_000)

    assert jwt.get_unverified_header(token) == {"alg": "HS256", "typ": "JWT"}


@pytest.mark.parametrize(
    ("decode_kwargs", "expected_error"),
    [
        pytest.param({"secret": TEST_SECRET + "-other"}, jwt.InvalidSignatureError, id="wrong-secret"),
        pytest.param({"audience": "terra-sense"}, jwt.InvalidAudienceError, id="wrong-audience"),
        pytest.param({"issuer": "untrusted-issuer"}, jwt.InvalidIssuerError, id="wrong-issuer"),
        pytest.param({"options": {}}, jwt.ExpiredSignatureError, id="expired"),
    ],
)
def test_service_token_verification_fails_closed(decode_kwargs, expected_error):
    token = ServiceTokenProvider(config()).get_token(now=1_000)

    with pytest.raises(expected_error):
        _decode(token, **decode_kwargs)


def test_tampered_scope_is_rejected():
    token = ServiceTokenProvider(config()).get_token(now=1_000)
    header, _, signature = token.split(".")
    escalated = jwt.utils.base64url_encode(
        json.dumps({**_unverified_claims(token), "scope": "admin"}).encode("utf-8")
    ).decode("ascii")

    with pytest.raises(jwt.InvalidSignatureError):
        _decode(f"{header}.{escalated}.{signature}")


@pytest.mark.parametrize(
    ("algorithm", "key"),
    [("none", None), ("HS512", TEST_SECRET)],
    ids=["alg-none", "alg-hs512"],
)
def test_algorithms_outside_the_hs256_allow_list_are_rejected(algorithm, key):
    claims = _unverified_claims(ServiceTokenProvider(config()).get_token(now=1_000))
    forged = jwt.encode(claims, key, algorithm=algorithm)

    with pytest.raises(jwt.InvalidAlgorithmError):
        _decode(forged)


def test_public_key_material_cannot_be_used_as_hmac_secret():
    with pytest.raises(jwt.InvalidKeyError):
        jwt.encode({"sub": "terra-cortex"}, TEST_ONLY_PUBLIC_KEY_PEM, algorithm="HS256")


@pytest.mark.parametrize("secret", ["", "x" * 31])
def test_service_auth_config_rejects_short_secrets(monkeypatch, secret):
    monkeypatch.delenv("SERVICE_AUTH_TOKEN_TTL_SECONDS", raising=False)
    monkeypatch.setenv("SERVICE_AUTH_JWT_SECRET", secret)

    with pytest.raises(ValueError, match="at least 32 bytes"):
        ServiceAuthConfig.from_env()
