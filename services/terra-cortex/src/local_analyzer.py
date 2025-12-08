"""
Local Edge AI Analyzer
Fast, rule-based anomaly detection (no external API calls)
This mimics "Edge AI" - instant local decisions without cloud dependency
"""
from datetime import datetime
from src.models import SensorData, Insight


class LocalAnalyzer:
    """
    Rule-based local anomaly detector for Edge AI processing.
    Fast, free, and works offline.
    """
    
    # Thresholds (configurable)
    TEMPERATURE_HIGH = 30.0  # Celsius
    TEMPERATURE_CRITICAL = 35.0
    HUMIDITY_LOW = 40.0  # Percent
    HUMIDITY_CRITICAL = 30.0
    CO2_HIGH = 800.0  # ppm
    CO2_CRITICAL = 1000.0
    SOIL_MOISTURE_LOW = 30.0  # Percent
    SOIL_MOISTURE_CRITICAL = 20.0
    LIGHT_LOW = 200.0  # lux
    LIGHT_HIGH = 800.0
    
    def __init__(self):
        """Initialize local analyzer with default thresholds"""
        self.analysis_count = 0
    
    def analyze(self, sensor_data: SensorData) -> Insight:
        """
        Perform fast local analysis on sensor data.
        
        Args:
            sensor_data: SensorData object with sensor readings
            
        Returns:
            Insight object with local analysis result
        """
        self.analysis_count += 1
        
        sensor_type = sensor_data.sensorType.lower()
        value = sensor_data.value
        
        # Initialize defaults
        status = "NORMAL"
        severity = "info"
        message = f"{sensor_data.sensorType} is within normal range"
        confidence = 0.95
        
        # Apply rule-based logic for each sensor type
        if sensor_type == "temperature":
            status, severity, message, confidence = self._analyze_temperature(value)
        
        elif sensor_type == "humidity":
            status, severity, message, confidence = self._analyze_humidity(value)
        
        elif sensor_type == "co2":
            status, severity, message, confidence = self._analyze_co2(value)
        
        elif sensor_type == "soilmoisture":
            status, severity, message, confidence = self._analyze_soil_moisture(value)
        
        elif sensor_type == "light":
            status, severity, message, confidence = self._analyze_light(value)
        
        # Create insight object
        insight = Insight(
            farmId=sensor_data.farmId,
            sensorType=sensor_data.sensorType,
            status=status,
            severity=severity,
            message=message,
            confidence=confidence,
            detectedAt=datetime.utcnow(),
            rawValue=value,
            llmRecommendation=None  # Will be filled by cloud_advisor if needed
        )
        
        return insight
    
    def _analyze_temperature(self, value: float) -> tuple[str, str, str, float]:
        """Analyze temperature reading"""
        if value > self.TEMPERATURE_CRITICAL:
            return (
                "ANOMALY",
                "critical",
                f"🔥 Temperature is critically high: {value}°C (critical threshold: {self.TEMPERATURE_CRITICAL}°C)",
                0.95
            )
        elif value > self.TEMPERATURE_HIGH:
            return (
                "ANOMALY",
                "warning",
                f"🌡️ Temperature is above normal: {value}°C (threshold: {self.TEMPERATURE_HIGH}°C)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"Temperature is normal: {value}°C", 0.95)
    
    def _analyze_humidity(self, value: float) -> tuple[str, str, str, float]:
        """Analyze humidity reading"""
        if value < self.HUMIDITY_CRITICAL:
            return (
                "ANOMALY",
                "critical",
                f"💧 Humidity is critically low: {value}% (critical threshold: {self.HUMIDITY_CRITICAL}%)",
                0.95
            )
        elif value < self.HUMIDITY_LOW:
            return (
                "ANOMALY",
                "warning",
                f"💨 Humidity is below normal: {value}% (threshold: {self.HUMIDITY_LOW}%)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"Humidity is normal: {value}%", 0.95)
    
    def _analyze_co2(self, value: float) -> tuple[str, str, str, float]:
        """Analyze CO2 reading"""
        if value > self.CO2_CRITICAL:
            return (
                "ANOMALY",
                "critical",
                f"⚠️ CO2 level is critically high: {value} ppm (critical threshold: {self.CO2_CRITICAL} ppm)",
                0.95
            )
        elif value > self.CO2_HIGH:
            return (
                "ANOMALY",
                "warning",
                f"🌫️ CO2 level is elevated: {value} ppm (threshold: {self.CO2_HIGH} ppm)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"CO2 level is normal: {value} ppm", 0.95)
    
    def _analyze_soil_moisture(self, value: float) -> tuple[str, str, str, float]:
        """Analyze soil moisture reading"""
        if value < self.SOIL_MOISTURE_CRITICAL:
            return (
                "ANOMALY",
                "critical",
                f"🏜️ Soil moisture is critically low: {value}% (critical threshold: {self.SOIL_MOISTURE_CRITICAL}%)",
                0.95
            )
        elif value < self.SOIL_MOISTURE_LOW:
            return (
                "ANOMALY",
                "warning",
                f"🌵 Soil moisture is below normal: {value}% (threshold: {self.SOIL_MOISTURE_LOW}%)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"Soil moisture is normal: {value}%", 0.95)
    
    def _analyze_light(self, value: float) -> tuple[str, str, str, float]:
        """Analyze light reading"""
        if value < self.LIGHT_LOW:
            return (
                "ANOMALY",
                "warning",
                f"🌙 Light level is low: {value} lux (threshold: {self.LIGHT_LOW} lux)",
                0.85
            )
        elif value > self.LIGHT_HIGH:
            return (
                "ANOMALY",
                "warning",
                f"☀️ Light level is high: {value} lux (threshold: {self.LIGHT_HIGH} lux)",
                0.85
            )
        else:
            return ("NORMAL", "info", f"Light level is normal: {value} lux", 0.95)
    
    def get_stats(self) -> dict:
        """Get analyzer statistics"""
        return {
            "total_analyses": self.analysis_count,
            "analyzer_type": "local_edge_ai",
            "mode": "rule-based"
        }
