"""
AI Analysis Logic (MVP - Dummy Logic)
Rule-based anomaly detection for sensor data
"""
from datetime import datetime
from src.models import SensorData, Insight


def analyze_sensor_data(sensor_data: SensorData) -> Insight:
    """
    Analyze sensor data and return insight
    
    MVP Logic:
    - If temperature > 30: ANOMALY
    - If humidity < 40: ANOMALY
    - Otherwise: NORMAL
    
    Args:
        sensor_data: SensorData object with sensor readings
        
    Returns:
        Insight object with analysis result
    """
    sensor_type = sensor_data.sensorType.lower()
    value = sensor_data.value
    
    # Initialize status and severity
    status = "NORMAL"
    severity = "info"
    message = f"{sensor_data.sensorType} is within normal range"
    confidence = 0.95
    
    # Apply MVP rules
    if sensor_type == "temperature" and value > 30:
        status = "ANOMALY"
        severity = "warning" if value <= 35 else "critical"
        message = f"🔥 Temperature is too high: {value}°C (threshold: 30°C)"
        confidence = 0.90
    
    elif sensor_type == "humidity" and value < 40:
        status = "ANOMALY"
        severity = "warning" if value >= 30 else "critical"
        message = f"💧 Humidity is too low: {value}% (threshold: 40%)"
        confidence = 0.90
    
    # Create insight object
    insight = Insight(
        farmId=sensor_data.farmId,
        sensorType=sensor_data.sensorType,
        status=status,
        severity=severity,
        message=message,
        confidence=confidence,
        detectedAt=datetime.utcnow(),
        rawValue=value
    )
    
    return insight
