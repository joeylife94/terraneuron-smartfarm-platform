"""Authenticated Terra-Ops crop profile integration."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from src.crop_profile import CropContext, CropProfileProvider, logger
from src.service_auth import ServiceTokenProvider, get_service_token_provider


class AuthenticatedCropProfileProvider(CropProfileProvider):
    """Adds a scoped, short-lived service JWT to Terra-Ops requests."""

    def __init__(self, token_provider: Optional[ServiceTokenProvider] = None):
        super().__init__()
        self.token_provider = token_provider or get_service_token_provider()
        self.auth_error_count = 0

    async def get_crop_context(self, farm_id: str) -> Optional[CropContext]:
        now = time.time()
        if farm_id in self._cache:
            context, cached_at = self._cache[farm_id]
            if (now - cached_at) < self.cache_ttl:
                self.cache_hit_count += 1
                return context

        try:
            self.fetch_count += 1
            url = f"{self.base_url}/api/farms/{farm_id}/optimal-conditions"
            headers = self.token_provider.authorization_headers()

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

            crop_context = self._parse_response(farm_id, data)
            self._cache[farm_id] = (crop_context, now)
            return crop_context

        except httpx.HTTPStatusError as exc:
            self.error_count += 1
            if exc.response.status_code in (401, 403):
                self.auth_error_count += 1
                logger.error(
                    "Crop profile service authentication rejected for farm=%s status=%s",
                    farm_id,
                    exc.response.status_code,
                )
            else:
                logger.error(
                    "Crop profile HTTP error for farm=%s status=%s",
                    farm_id,
                    exc.response.status_code,
                )
            return self._stale_or_fallback(farm_id)
        except httpx.ConnectError:
            self.error_count += 1
            logger.warning(
                "terra-ops unreachable (%s). Using default thresholds.",
                self.base_url,
            )
            return self._stale_or_fallback(farm_id)
        except Exception as exc:
            self.error_count += 1
            logger.error("Crop profile fetch error for %s: %s", farm_id, exc)
            return self._stale_or_fallback(farm_id)

    def _stale_or_fallback(self, farm_id: str) -> CropContext:
        if farm_id in self._cache:
            return self._cache[farm_id][0]
        return self._fallback_context(farm_id)

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        stats.update(
            {
                "service_auth_enabled": True,
                "service_auth_errors": self.auth_error_count,
                "service_auth": self.token_provider.get_stats(),
            }
        )
        return stats


_provider: Optional[AuthenticatedCropProfileProvider] = None


def get_authenticated_crop_profile_provider() -> AuthenticatedCropProfileProvider:
    global _provider
    if _provider is None:
        _provider = AuthenticatedCropProfileProvider()
    return _provider
