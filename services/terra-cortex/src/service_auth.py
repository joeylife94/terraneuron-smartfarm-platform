"""Short-lived JWT credentials for Terra-Cortex to call Terra-Ops."""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

import jwt


@dataclass(frozen=True)
class ServiceAuthConfig:
    secret: str
    issuer: str = "terraneuron-internal"
    audience: str = "terra-ops"
    subject: str = "terra-cortex"
    scope: str = "crop:read"
    ttl_seconds: int = 60
    refresh_skew_seconds: int = 10

    @classmethod
    def from_env(cls) -> "ServiceAuthConfig":
        ttl = int(os.getenv("SERVICE_AUTH_TOKEN_TTL_SECONDS", "60"))
        if ttl < 30 or ttl > 300:
            raise ValueError("SERVICE_AUTH_TOKEN_TTL_SECONDS must be between 30 and 300")

        secret = os.getenv("SERVICE_AUTH_JWT_SECRET", "")
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("SERVICE_AUTH_JWT_SECRET must be at least 32 bytes")

        return cls(
            secret=secret,
            issuer=os.getenv("SERVICE_AUTH_JWT_ISSUER", "terraneuron-internal"),
            audience=os.getenv("SERVICE_AUTH_JWT_AUDIENCE", "terra-ops"),
            subject=os.getenv("SERVICE_AUTH_SUBJECT", "terra-cortex"),
            scope=os.getenv("SERVICE_AUTH_SCOPE", "crop:read"),
            ttl_seconds=ttl,
        )


class ServiceTokenProvider:
    """Caches a service JWT while keeping its lifetime deliberately short."""

    def __init__(self, config: Optional[ServiceAuthConfig] = None):
        self.config = config or ServiceAuthConfig.from_env()
        self._lock = threading.Lock()
        self._cached_token: Optional[str] = None
        self._cached_expiry = 0
        self.issued_count = 0

    def authorization_headers(self, now: Optional[int] = None) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.get_token(now=now)}"}

    def get_token(self, now: Optional[int] = None) -> str:
        issued_at = int(time.time() if now is None else now)
        with self._lock:
            if (
                self._cached_token
                and issued_at < self._cached_expiry - self.config.refresh_skew_seconds
            ):
                return self._cached_token

            expiry = issued_at + self.config.ttl_seconds
            payload: Dict[str, Any] = {
                "iss": self.config.issuer,
                "aud": self.config.audience,
                "sub": self.config.subject,
                "type": "service",
                "scope": self.config.scope,
                "iat": issued_at,
                "nbf": issued_at - 1,
                "exp": expiry,
                "jti": str(uuid.uuid4()),
            }
            self._cached_token = jwt.encode(
                payload,
                self.config.secret,
                algorithm="HS256",
            )
            self._cached_expiry = expiry
            self.issued_count += 1
            return self._cached_token

    def get_stats(self) -> Dict[str, Any]:
        return {
            "issuer": self.config.issuer,
            "audience": self.config.audience,
            "subject": self.config.subject,
            "scope": self.config.scope,
            "ttl_seconds": self.config.ttl_seconds,
            "issued_tokens": self.issued_count,
        }


_provider: Optional[ServiceTokenProvider] = None


def get_service_token_provider() -> ServiceTokenProvider:
    global _provider
    if _provider is None:
        _provider = ServiceTokenProvider()
    return _provider
