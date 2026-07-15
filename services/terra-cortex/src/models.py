"""
Pydantic models for Terra-Cortex service.
"""

import math
from datetime import datetime
from typing import ClassVar, Optional

from pydantic import BaseModel, field_validator


class SensorData(BaseModel):
    """Input sensor data model from Kafka."""

    SUPPORTED_SENSOR_TYPES: ClassVar[frozenset[str]] = frozenset(
        {"temperature", "humidity", "co2", "soilMoisture", "light"}
    )

    farmId: str
    sensorType: str
    value: float
    timestamp: Optional[datetime] = None

    @field_validator("farmId")
    @classmethod
    def validate_farm_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("farmId must not be blank")
        return normalized

    @field_validator("sensorType")
    @classmethod
    def validate_sensor_type(cls, value: str) -> str:
        normalized = value.strip()
        if normalized not in cls.SUPPORTED_SENSOR_TYPES:
            supported = ", ".join(sorted(cls.SUPPORTED_SENSOR_TYPES))
            raise ValueError(
                f"unsupported sensorType '{value}'; expected one of: {supported}"
            )
        return normalized

    @field_validator("value")
    @classmethod
    def validate_finite_value(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("value must be a finite number")
        return value

    class Config:
        populate_by_name = True


class WeatherContext(BaseModel):
    """External weather data for context-aware analysis."""

    temperature: Optional[float] = None      # 외기 온도 (°C)
    humidity: Optional[float] = None         # 외기 습도 (%)
    description: Optional[str] = None        # 날씨 설명
    wind_speed: Optional[float] = None       # 풍속 (m/s)
    rain_1h: float = 0.0                     # 1시간 강수량 (mm)
    forecast_temp_max: Optional[float] = None # 오늘 최고 온도 예보
    forecast_temp_min: Optional[float] = None # 오늘 최저 온도 예보


class Insight(BaseModel):
    """Output insight model to Kafka."""

    farmId: str
    sensorType: str
    status: str  # NORMAL or ANOMALY
    severity: str  # info, warning, critical
    message: str
    confidence: float
    detectedAt: datetime
    rawValue: float
    llmRecommendation: Optional[str] = None  # Cloud LLM recommendation (only for ANOMALY)
    weatherContext: Optional[str] = None     # 날씨 컨텍스트 요약 (분석 시 참조된 외부 날씨)
    cropContext: Optional[str] = None        # 작물 컨텍스트 요약 (생장 단계별 최적 범위)
    trendContext: Optional[str] = None       # 시계열 추세 컨텍스트 (이동평균, 급변, 예측)

    class Config:
        populate_by_name = True
