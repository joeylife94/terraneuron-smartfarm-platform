from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SensorData(BaseModel):
    """센서 원시 데이터 모델"""
    sensor_id: str = Field(..., alias="sensorId")
    sensor_type: str = Field(..., alias="sensorType")
    value: float
    unit: Optional[str] = None
    farm_id: str = Field(..., alias="farmId")
    timestamp: datetime
    
    class Config:
        populate_by_name = True


class Insight(BaseModel):
    """AI 분석 결과 모델"""
    sensor_id: str = Field(..., alias="sensorId")
    insight_type: str = Field(..., alias="insightType")
    severity: str  # info, warning, critical
    message: str
    confidence_score: float = Field(..., alias="confidenceScore")
    detected_at: datetime = Field(..., alias="detectedAt")
    raw_data: Optional[dict] = Field(None, alias="rawData")
    
    class Config:
        populate_by_name = True
