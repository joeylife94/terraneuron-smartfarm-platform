import numpy as np
from typing import Tuple
from src.models import SensorData, Insight
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """간단한 이상 탐지 모델 (통계 기반)"""
    
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        # 센서 타입별 정상 범위 (실제로는 학습된 모델 사용)
        self.normal_ranges = {
            "temperature": (15.0, 30.0),
            "humidity": (40.0, 80.0),
            "co2": (300.0, 1000.0),
        }
    
    def detect(self, sensor_data: SensorData) -> Tuple[bool, float, str]:
        """
        이상 탐지 수행
        
        Returns:
            (is_anomaly, confidence_score, severity)
        """
        sensor_type = sensor_data.sensor_type.lower()
        value = sensor_data.value
        
        if sensor_type not in self.normal_ranges:
            logger.warning(f"알 수 없는 센서 타입: {sensor_type}")
            return False, 0.0, "info"
        
        min_val, max_val = self.normal_ranges[sensor_type]
        
        # 정상 범위 체크
        if min_val <= value <= max_val:
            return False, 0.95, "info"
        
        # 이상치 심각도 계산
        if value < min_val:
            deviation = (min_val - value) / min_val
        else:
            deviation = (value - max_val) / max_val
        
        confidence = min(0.95, 0.7 + deviation * 0.5)
        
        if deviation > 0.5:
            severity = "critical"
        elif deviation > 0.2:
            severity = "warning"
        else:
            severity = "info"
        
        return True, confidence, severity
    
    def create_insight(self, sensor_data: SensorData) -> Insight:
        """센서 데이터를 분석하여 인사이트 생성"""
        
        is_anomaly, confidence, severity = self.detect(sensor_data)
        
        if is_anomaly:
            message = self._generate_anomaly_message(sensor_data)
            insight_type = "anomaly"
        else:
            message = f"{sensor_data.sensor_type} 센서가 정상 범위 내에 있습니다."
            insight_type = "normal"
        
        return Insight(
            sensor_id=sensor_data.sensor_id,
            insight_type=insight_type,
            severity=severity,
            message=message,
            confidence_score=confidence,
            detected_at=datetime.utcnow(),
            raw_data={
                "value": sensor_data.value,
                "unit": sensor_data.unit,
                "type": sensor_data.sensor_type
            }
        )
    
    def _generate_anomaly_message(self, sensor_data: SensorData) -> str:
        """이상 상태에 대한 메시지 생성"""
        sensor_type = sensor_data.sensor_type
        value = sensor_data.value
        unit = sensor_data.unit or ""
        
        min_val, max_val = self.normal_ranges.get(sensor_type.lower(), (0, 0))
        
        if value < min_val:
            return f"⚠️ {sensor_type} 센서 값이 정상 범위보다 낮습니다. (현재: {value}{unit}, 정상: {min_val}-{max_val}{unit})"
        else:
            return f"🔥 {sensor_type} 센서 값이 정상 범위를 초과했습니다. (현재: {value}{unit}, 정상: {min_val}-{max_val}{unit})"
