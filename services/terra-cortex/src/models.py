"""
Pydantic models for Terra-Cortex service
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SensorData(BaseModel):
    """Input sensor data model from Kafka"""
    farmId: str
    sensorType: str
    value: float
    timestamp: Optional[datetime] = None
    
    class Config:
        populate_by_name = True


class WeatherContext(BaseModel):
    """External weather data for context-aware analysis"""
    temperature: Optional[float] = None      # 외기 온도 (°C)
    humidity: Optional[float] = None         # 외기 습도 (%)
    description: Optional[str] = None        # 날씨 설명
    wind_speed: Optional[float] = None       # 풍속 (m/s)
    rain_1h: float = 0.0                     # 1시간 강수량 (mm)
    forecast_temp_max: Optional[float] = None # 오늘 최고 기온 예보
    forecast_temp_min: Optional[float] = None # 오늘 최저 기온 예보


class Insight(BaseModel):
    """Output insight model to Kafka"""
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
