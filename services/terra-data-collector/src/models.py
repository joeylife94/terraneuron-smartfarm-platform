"""
Terra Data Collector - Pydantic Models
TerraNeuron 센서 데이터 포맷과 호환되는 정규화 모델
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field


class DataSource(str, Enum):
    """데이터 소스 구분 (IoT vs 외부)"""
    IOT = "iot"
    EXTERNAL = "external"


class DataProvider(str, Enum):
    """외부 데이터 제공자"""
    OPEN_METEO = "open_meteo"
    NASA_POWER = "nasa_power"
    THINGSPEAK = "thingspeak"


class DataQuality(str, Enum):
    """데이터 품질 등급"""
    HIGH = "high"          # 공인 기상대, 검증된 API
    MEDIUM = "medium"      # 공개 IoT 센서 (ThingSpeak)
    LOW = "low"            # 스크래핑, 비검증 소스


class SensorType(str, Enum):
    """센서 타입 (terra-sense 호환)"""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    CO2 = "co2"
    SOIL_MOISTURE = "soilMoisture"
    LIGHT = "light"


# ============ 수집 데이터 모델 ============

class CollectedSensorData(BaseModel):
    """
    수집된 센서 데이터 (정규화 모델)
    terra-sense의 SensorData와 호환되면서 메타데이터 추가
    """
    # terra-sense 호환 필드
    sensorId: str = Field(..., description="센서 ID (provider-type-idx)")
    sensorType: str = Field(..., description="센서 타입")
    value: float = Field(..., description="센서 값")
    unit: str = Field(..., description="단위")
    farmId: str = Field(..., description="매핑된 농장 ID")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        description="ISO8601 타임스탬프"
    )

    # 외부 데이터 메타 필드 (terra-sense 전송 시 제거 가능)
    source: DataSource = Field(default=DataSource.EXTERNAL, description="데이터 소스 구분")
    provider: Optional[str] = Field(default=None, description="데이터 제공자")
    quality: DataQuality = Field(default=DataQuality.HIGH, description="데이터 품질")
    location: Optional[Dict[str, float]] = Field(default=None, description="위치 정보")
    raw_variable: Optional[str] = Field(default=None, description="원본 변수명")

    def to_terra_sense_payload(self) -> Dict[str, Any]:
        """terra-sense API 호환 페이로드 (메타데이터 제거)"""
        return {
            "sensorId": self.sensorId,
            "sensorType": self.sensorType,
            "value": self.value,
            "unit": self.unit,
            "farmId": self.farmId,
            "timestamp": self.timestamp,
        }

    def to_kafka_payload(self) -> Dict[str, Any]:
        """Kafka raw-sensor-data 토픽 호환 페이로드"""
        return self.to_terra_sense_payload()

    def to_training_record(self) -> Dict[str, Any]:
        """AI 학습용 전체 레코드 (메타데이터 포함)"""
        return self.model_dump(mode='json')

    def to_finetune_instruction(self) -> Dict[str, str]:
        """LLM 파인튜닝용 instruction 포맷"""
        instruction = (
            f"다음은 스마트팜 센서 데이터입니다. 분석하세요:\n"
            f"농장: {self.farmId}, 센서: {self.sensorType}, 값: {self.value}{self.unit}"
        )

        # 간단한 규칙 기반 레이블 생성
        analysis = self._generate_analysis_label()

        return {
            "instruction": instruction,
            "input": f"{self.sensorType}={self.value}{self.unit}",
            "output": analysis,
        }

    def _generate_analysis_label(self) -> str:
        """학습 레이블 생성 (자동 어노테이션)"""
        thresholds = {
            "temperature": {"low": 10, "high": 30, "critical": 35, "unit": "°C"},
            "humidity": {"low": 40, "high": 80, "critical": 90, "unit": "%"},
            "co2": {"low": 200, "high": 800, "critical": 1000, "unit": "ppm"},
            "soilMoisture": {"low": 20, "high": 70, "critical": 85, "unit": "%"},
            "light": {"low": 100, "high": 800, "critical": 1200, "unit": "lux"},
        }

        t = thresholds.get(self.sensorType)
        if not t:
            return f"{self.sensorType} 값 {self.value}: 분석 데이터 부족"

        v = self.value
        if v >= t["critical"]:
            return (
                f"[위험] {self.sensorType} {v}{t['unit']}로 임계치({t['critical']}{t['unit']}) 초과. "
                f"즉시 조치 필요. 환기 및 냉각 시스템 가동 권장."
            )
        elif v >= t["high"]:
            return (
                f"[경고] {self.sensorType} {v}{t['unit']}로 정상 범위 상한({t['high']}{t['unit']}) 초과. "
                f"모니터링 강화 필요."
            )
        elif v <= t["low"]:
            return (
                f"[주의] {self.sensorType} {v}{t['unit']}로 정상 범위 하한({t['low']}{t['unit']}) 미달. "
                f"보조 장치 가동 검토."
            )
        else:
            return f"[정상] {self.sensorType} {v}{t['unit']}로 정상 범위 내. 현 상태 유지."


# ============ 수집 작업 결과 모델 ============

class CollectionResult(BaseModel):
    """단일 수집 작업 결과"""
    provider: str
    farm_id: str
    records_collected: int = 0
    records_exported: int = 0
    errors: List[str] = Field(default_factory=list)
    duration_ms: float = 0
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CollectionSummary(BaseModel):
    """전체 수집 세션 요약"""
    session_id: str
    started_at: str
    completed_at: Optional[str] = None
    providers_used: List[str] = Field(default_factory=list)
    total_records: int = 0
    total_exported: int = 0
    total_errors: int = 0
    results: List[CollectionResult] = Field(default_factory=list)


# ============ 설정 모델 ============

class FarmConfig(BaseModel):
    """농장 설정"""
    farm_id: str
    name: str
    latitude: float
    longitude: float


class ProviderConfig(BaseModel):
    """제공자 기본 설정"""
    enabled: bool = True
    interval_seconds: int = 300
