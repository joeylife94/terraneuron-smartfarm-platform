"""
Crop Profile Provider for Terra-Cortex
terra-ops REST API를 호출하여 농장별 작물/생장단계 최적 환경 조건을 조회

사용 흐름:
  1. Kafka 메시지의 farmId로 crop context 조회
  2. terra-ops GET /api/farms/{farmId}/optimal-conditions 호출
  3. TTL 캐시로 불필요한 API 호출 방지 (생장단계는 느리게 변함)
  4. local_analyzer / cloud_advisor에 CropContext 전달
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)

# Configuration
TERRA_OPS_URL = os.getenv("TERRA_OPS_URL", "http://terra-ops:8080")
CROP_CACHE_TTL = int(os.getenv("CROP_CACHE_TTL", "1800"))  # 30분 (생장단계 변화 느림)


@dataclass
class SensorRange:
    """센서 유형별 최적 범위"""
    min: float
    optimal_low: float   # 온도/습도: 4-point range
    optimal_high: float
    max: float

    @classmethod
    def from_4point(cls, data: Dict[str, float]) -> "SensorRange":
        return cls(
            min=data.get("min", 0),
            optimal_low=data.get("optimalLow", data.get("optimal", 0)),
            optimal_high=data.get("optimalHigh", data.get("optimal", 0)),
            max=data.get("max", 100),
        )

    @classmethod
    def from_3point(cls, data: Dict[str, float]) -> "SensorRange":
        """CO2, light, soilMoisture: min/optimal/max → 4-point 변환"""
        optimal = data.get("optimal", 0)
        return cls(
            min=data.get("min", 0),
            optimal_low=optimal * 0.9,   # optimal의 ±10%를 적정 범위로 설정
            optimal_high=optimal * 1.1,
            max=data.get("max", 100),
        )


@dataclass
class CropCondition:
    """단일 작물/존의 현재 최적 환경 조건"""
    crop_code: str
    crop_name: str
    zone: str
    current_stage: str
    stage_code: str
    stage_order: int
    days_since_planting: int
    temperature: SensorRange
    humidity: SensorRange
    co2: SensorRange
    light: SensorRange
    soil_moisture: SensorRange
    notes: Optional[str] = None

    def to_context_string(self) -> str:
        """분석 파이프라인용 컨텍스트 문자열"""
        return (
            f"작물: {self.crop_name}({self.crop_code}) | "
            f"생장단계: {self.current_stage}(#{self.stage_order}) | "
            f"재배 {self.days_since_planting}일차 | "
            f"적정온도: {self.temperature.optimal_low}~{self.temperature.optimal_high}°C | "
            f"적정습도: {self.humidity.optimal_low}~{self.humidity.optimal_high}% | "
            f"적정CO2: {self.co2.optimal_low:.0f}~{self.co2.optimal_high:.0f}ppm"
        )


@dataclass
class CropContext:
    """농장의 전체 작물 컨텍스트"""
    farm_id: str
    has_crop_profile: bool
    crops: List[CropCondition] = field(default_factory=list)
    message: Optional[str] = None

    def get_condition_for_zone(self, zone: str) -> Optional[CropCondition]:
        """특정 존의 작물 조건 반환"""
        for c in self.crops:
            if c.zone == zone:
                return c
        return None

    def get_primary_condition(self) -> Optional[CropCondition]:
        """첫 번째 (주력) 작물 조건 반환"""
        return self.crops[0] if self.crops else None

    def to_context_string(self) -> str:
        """분석 파이프라인용 컨텍스트 문자열"""
        if not self.has_crop_profile:
            return f"농장 {self.farm_id}: 등록된 작물 프로필 없음 (기본 임계값 사용)"
        parts = [f"농장 {self.farm_id} 작물 현황:"]
        for c in self.crops:
            parts.append(f"  - {c.to_context_string()}")
        return "\n".join(parts)


class CropProfileProvider:
    """
    terra-ops 연동 작물 프로필 제공자 (TTL 캐시 내장)
    """

    def __init__(self):
        self.base_url = TERRA_OPS_URL
        self.cache_ttl = CROP_CACHE_TTL
        self.enabled = True  # terra-ops가 실행 중이면 항상 활성

        # farmId → (CropContext, fetch_time)
        self._cache: Dict[str, tuple[CropContext, float]] = {}

        # 통계
        self.fetch_count = 0
        self.cache_hit_count = 0
        self.error_count = 0

        logger.info(
            f"✅ CropProfileProvider initialized: "
            f"terra-ops={self.base_url}, cache_ttl={self.cache_ttl}s"
        )

    async def get_crop_context(self, farm_id: str) -> Optional[CropContext]:
        """
        농장 ID로 현재 작물/생장단계 최적 조건 조회

        Args:
            farm_id: 농장 식별자 (e.g., "farm-A")

        Returns:
            CropContext or None (오류 시)
        """
        # 캐시 확인
        now = time.time()
        if farm_id in self._cache:
            ctx, cached_at = self._cache[farm_id]
            if (now - cached_at) < self.cache_ttl:
                self.cache_hit_count += 1
                logger.debug(f"🔄 Crop cache hit: {farm_id} (age: {int(now - cached_at)}s)")
                return ctx

        # terra-ops API 호출
        try:
            self.fetch_count += 1
            url = f"{self.base_url}/api/farms/{farm_id}/optimal-conditions"

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

            crop_ctx = self._parse_response(farm_id, data)
            self._cache[farm_id] = (crop_ctx, now)

            if crop_ctx.has_crop_profile:
                logger.info(
                    f"🌱 Crop context loaded: {farm_id} → "
                    f"{len(crop_ctx.crops)} crops"
                )
            else:
                logger.debug(f"🌱 No crop profile for {farm_id}")

            return crop_ctx

        except httpx.ConnectError:
            self.error_count += 1
            logger.warning(f"⚠️ terra-ops unreachable ({self.base_url}). Using default thresholds.")
            return self._fallback_context(farm_id)
        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Crop profile fetch error for {farm_id}: {e}")
            # 이전 캐시가 있으면 만료되었더라도 반환 (graceful degradation)
            if farm_id in self._cache:
                return self._cache[farm_id][0]
            return self._fallback_context(farm_id)

    def _parse_response(self, farm_id: str, data: Dict[str, Any]) -> CropContext:
        """terra-ops JSON 응답을 CropContext로 파싱"""
        has_profile = data.get("hasCropProfile", False)

        if not has_profile:
            return CropContext(
                farm_id=farm_id,
                has_crop_profile=False,
                message=data.get("message", ""),
            )

        crops = []
        for crop_data in data.get("crops", []):
            condition = CropCondition(
                crop_code=crop_data.get("cropCode", ""),
                crop_name=crop_data.get("cropName", ""),
                zone=crop_data.get("zone", ""),
                current_stage=crop_data.get("currentStage", ""),
                stage_code=crop_data.get("stageCode", ""),
                stage_order=crop_data.get("stageOrder", 1),
                days_since_planting=crop_data.get("daysSincePlanting", 0),
                temperature=SensorRange.from_4point(crop_data.get("temperature", {})),
                humidity=SensorRange.from_4point(crop_data.get("humidity", {})),
                co2=SensorRange.from_3point(crop_data.get("co2", {})),
                light=SensorRange.from_3point(crop_data.get("light", {})),
                soil_moisture=SensorRange.from_3point(crop_data.get("soilMoisture", {})),
                notes=crop_data.get("notes"),
            )
            crops.append(condition)

        return CropContext(
            farm_id=farm_id,
            has_crop_profile=True,
            crops=crops,
        )

    def _fallback_context(self, farm_id: str) -> CropContext:
        """terra-ops 연결 불가 시 폴백 (기본 임계값 사용 신호)"""
        return CropContext(
            farm_id=farm_id,
            has_crop_profile=False,
            message="terra-ops 미연결. 기본 임계값 사용.",
        )

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            "provider": "terra-ops",
            "base_url": self.base_url,
            "enabled": self.enabled,
            "cache_ttl": self.cache_ttl,
            "total_fetches": self.fetch_count,
            "cache_hits": self.cache_hit_count,
            "errors": self.error_count,
            "cached_farms": list(self._cache.keys()),
        }


# Singleton factory
_provider: Optional[CropProfileProvider] = None


def get_crop_profile_provider() -> CropProfileProvider:
    """싱글톤 CropProfileProvider 반환"""
    global _provider
    if _provider is None:
        _provider = CropProfileProvider()
    return _provider
