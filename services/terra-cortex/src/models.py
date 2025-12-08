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
    
    class Config:
        populate_by_name = True
