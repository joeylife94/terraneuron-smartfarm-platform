"""
Local Edge AI Analyzer
Fast, rule-based anomaly detection (no external API calls)
This mimics "Edge AI" - instant local decisions without cloud dependency
Enhanced: 작물 프로필 기반 동적 임계값 (Step 2)
"""
from datetime import datetime
from typing import Optional
from src.models import SensorData, Insight
from src.weather_provider import WeatherData
from src.crop_profile import CropContext, CropCondition
from src.timeseries import TrendContext


class LocalAnalyzer:
    """
    Rule-based local anomaly detector for Edge AI processing.
    Fast, free, and works offline.
    작물 프로필이 있으면 생장 단계별 최적 범위를 임계값으로 사용.
    """
    
    # Default Thresholds (작물 프로필이 없을 때 사용)
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
        self._current_weather: Optional[WeatherData] = None
        self._current_crop: Optional[CropContext] = None
        self._current_trend: Optional[TrendContext] = None
    
    def set_weather_context(self, weather: Optional[WeatherData]):
        """외부 날씨 데이터를 설정하여 임계값 동적 조정에 활용"""
        self._current_weather = weather
    
    def set_crop_context(self, crop_ctx: Optional[CropContext]):
        """작물 프로필 컨텍스트 설정 (생장 단계별 최적 범위 적용)"""
        self._current_crop = crop_ctx
    
    def set_trend_context(self, trend_ctx: Optional[TrendContext]):
        """시계열 추세 컨텍스트 설정 (이동평균, 급변, 예측)"""
        self._current_trend = trend_ctx
    
    def _get_crop_condition(self) -> Optional[CropCondition]:
        """현재 작물 조건 반환 (주력 작물 우선)"""
        if self._current_crop and self._current_crop.has_crop_profile:
            return self._current_crop.get_primary_condition()
        return None
    
    def _get_adjusted_thresholds(self):
        """
        날씨 기반 동적 임계값 조정
        - 외기 온도가 높으면 → 실내 온도 임계값 완화 (냉방 한계 고려)
        - 비 오는 날 → 습도 임계값 완화 (외부 습도 유입 고려)
        - 외기 온도가 낮을 때 → 난방 부하 경고 추가
        """
        temp_high = self.TEMPERATURE_HIGH
        temp_critical = self.TEMPERATURE_CRITICAL
        humidity_low = self.HUMIDITY_LOW
        humidity_critical = self.HUMIDITY_CRITICAL
        
        if self._current_weather:
            outdoor_temp = self._current_weather.temperature
            outdoor_humidity = self._current_weather.humidity
            rain = self._current_weather.rain_1h
            
            # 폭염(35°C+) 시 실내 온도 임계값 2도 완화
            if outdoor_temp >= 35:
                temp_high += 2.0
                temp_critical += 2.0
            # 한파(-5°C 이하) 시 실내 온도 하한 경고 추가 (별도 처리)
            
            # 강수 시 습도 임계값 5% 완화
            if rain > 0:
                humidity_low -= 5.0
                humidity_critical -= 5.0
            
            # 외기 습도가 80% 이상이면 실내 습도 하한 완화
            if outdoor_humidity >= 80:
                humidity_low -= 3.0
        
        return temp_high, temp_critical, humidity_low, humidity_critical
    
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
        
        # 날씨 기반 동적 임계값 가져오기
        adj_temp_h, adj_temp_c, adj_hum_l, adj_hum_c = self._get_adjusted_thresholds()
        
        # 작물 프로필 기반 동적 임계값 (우선순위: 작물 > 기본)
        crop_condition = self._get_crop_condition()
        
        # Apply rule-based logic for each sensor type
        if sensor_type == "temperature":
            if crop_condition:
                # 작물 생장 단계별 적정 온도 범위를 임계값으로 사용
                adj_temp_h = crop_condition.temperature.optimal_high
                adj_temp_c = crop_condition.temperature.max
            status, severity, message, confidence = self._analyze_temperature(value, adj_temp_h, adj_temp_c)
        
        elif sensor_type == "humidity":
            if crop_condition:
                adj_hum_l = crop_condition.humidity.optimal_low
                adj_hum_c = crop_condition.humidity.min
            status, severity, message, confidence = self._analyze_humidity(value, adj_hum_l, adj_hum_c)
        
        elif sensor_type == "co2":
            if crop_condition:
                status, severity, message, confidence = self._analyze_co2(
                    value, crop_condition.co2.optimal_high, crop_condition.co2.max
                )
            else:
                status, severity, message, confidence = self._analyze_co2(value)
        
        elif sensor_type == "soilmoisture":
            if crop_condition:
                status, severity, message, confidence = self._analyze_soil_moisture(
                    value, crop_condition.soil_moisture.optimal_low, crop_condition.soil_moisture.min
                )
            else:
                status, severity, message, confidence = self._analyze_soil_moisture(value)
        
        elif sensor_type == "light":
            if crop_condition:
                status, severity, message, confidence = self._analyze_light(
                    value, crop_condition.light.min, crop_condition.light.max
                )
            else:
                status, severity, message, confidence = self._analyze_light(value)
        
        # 날씨 컨텍스트 문자열 생성
        weather_ctx_str = None
        if self._current_weather:
            weather_ctx_str = self._current_weather.to_context_string()
            # 날씨 정보가 분석에 영향을 미쳤으면 메시지에 추가
            if self._current_weather.temperature >= 35:
                message += f" (폭염 주의: 외기 {self._current_weather.temperature}°C)"
            elif self._current_weather.rain_1h > 0:
                message += f" (강수 중: {self._current_weather.rain_1h}mm/h)"
        
        # 작물 컨텍스트가 있으면 메시지에 작물 정보 추가
        crop_ctx_str = None
        if crop_condition:
            crop_ctx_str = crop_condition.to_context_string()
            if status == "ANOMALY":
                message += (
                    f" [작물: {crop_condition.crop_name} "
                    f"{crop_condition.current_stage}({crop_condition.days_since_planting}일차)]"
                )
        
        # 시계열 추세 컨텍스트 반영
        trend_ctx_str = None
        if self._current_trend and self._current_trend.has_data and self._current_trend.stats:
            trend = self._current_trend.stats
            trend_ctx_str = self._current_trend.to_context_string()
            
            # 급변(spike) 감지 시 severity 상향
            if trend.is_spike and status == "NORMAL":
                status = "ANOMALY"
                severity = "warning"
                message = (
                    f"📈 급변 감지: {sensor_data.sensorType} {value} "
                    f"(이동평균 {trend.moving_avg}, 편차 {trend.deviation_from_ma:+.1f}, 2σ 초과)"
                )
                confidence = 0.85
            elif trend.is_spike and status == "ANOMALY":
                message += f" (급변: MA편차={trend.deviation_from_ma:+.1f})"
            
            # 상승 추세에서 예측값이 임계치 초과 시 사전 경고
            if (
                trend.predicted_next is not None
                and trend.direction == "rising"
                and status == "NORMAL"
            ):
                # 10분 후 예측값이 현재 임계값 초과할 것으로 보이면 주의
                pred = trend.predicted_next
                sensor_low = sensor_type.lower()
                will_exceed = False
                if sensor_low == "temperature" and pred > adj_temp_h:
                    will_exceed = True
                elif sensor_low == "co2" and pred > self.CO2_HIGH:
                    will_exceed = True
                
                if will_exceed:
                    status = "ANOMALY"
                    severity = "warning"
                    message = (
                        f"📊 예측 경고: {sensor_data.sensorType} 현재 {value}, "
                        f"10분 후 {pred:.1f} 예측 (추세: {trend.direction}, "
                        f"변화율: {trend.rate_of_change:+.2f}/h)"
                    )
                    confidence = 0.80
        
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
            llmRecommendation=None,  # Will be filled by cloud_advisor if needed
            weatherContext=weather_ctx_str,
            cropContext=crop_ctx_str,
            trendContext=trend_ctx_str
        )
        
        return insight
    
    def _analyze_temperature(self, value: float, threshold_high: float = None, threshold_critical: float = None) -> tuple[str, str, str, float]:
        """Analyze temperature reading with dynamic thresholds"""
        high = threshold_high or self.TEMPERATURE_HIGH
        critical = threshold_critical or self.TEMPERATURE_CRITICAL
        
        if value > critical:
            return (
                "ANOMALY",
                "critical",
                f"🔥 Temperature is critically high: {value}°C (critical threshold: {critical}°C)",
                0.95
            )
        elif value > high:
            return (
                "ANOMALY",
                "warning",
                f"🌡️ Temperature is above normal: {value}°C (threshold: {high}°C)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"Temperature is normal: {value}°C", 0.95)
    
    def _analyze_humidity(self, value: float, threshold_low: float = None, threshold_critical: float = None) -> tuple[str, str, str, float]:
        """Analyze humidity reading with dynamic thresholds"""
        low = threshold_low or self.HUMIDITY_LOW
        critical = threshold_critical or self.HUMIDITY_CRITICAL
        
        if value < critical:
            return (
                "ANOMALY",
                "critical",
                f"💧 Humidity is critically low: {value}% (critical threshold: {critical}%)",
                0.95
            )
        elif value < low:
            return (
                "ANOMALY",
                "warning",
                f"💨 Humidity is below normal: {value}% (threshold: {low}%)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"Humidity is normal: {value}%", 0.95)
    
    def _analyze_co2(self, value: float, threshold_high: float = None, threshold_critical: float = None) -> tuple[str, str, str, float]:
        """Analyze CO2 reading with optional crop-specific thresholds"""
        high = threshold_high or self.CO2_HIGH
        critical = threshold_critical or self.CO2_CRITICAL
        
        if value > critical:
            return (
                "ANOMALY",
                "critical",
                f"⚠️ CO2 level is critically high: {value} ppm (critical threshold: {critical} ppm)",
                0.95
            )
        elif value > high:
            return (
                "ANOMALY",
                "warning",
                f"🌫️ CO2 level is elevated: {value} ppm (threshold: {high} ppm)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"CO2 level is normal: {value} ppm", 0.95)
    
    def _analyze_soil_moisture(self, value: float, threshold_low: float = None, threshold_critical: float = None) -> tuple[str, str, str, float]:
        """Analyze soil moisture reading with optional crop-specific thresholds"""
        low = threshold_low or self.SOIL_MOISTURE_LOW
        critical = threshold_critical or self.SOIL_MOISTURE_CRITICAL
        
        if value < critical:
            return (
                "ANOMALY",
                "critical",
                f"🏜️ Soil moisture is critically low: {value}% (critical threshold: {critical}%)",
                0.95
            )
        elif value < low:
            return (
                "ANOMALY",
                "warning",
                f"🌵 Soil moisture is below normal: {value}% (threshold: {low}%)",
                0.90
            )
        else:
            return ("NORMAL", "info", f"Soil moisture is normal: {value}%", 0.95)
    
    def _analyze_light(self, value: float, threshold_low: float = None, threshold_high: float = None) -> tuple[str, str, str, float]:
        """Analyze light reading with optional crop-specific thresholds"""
        low = threshold_low or self.LIGHT_LOW
        high = threshold_high or self.LIGHT_HIGH
        
        if value < low:
            return (
                "ANOMALY",
                "warning",
                f"🌙 Light level is low: {value} lux (threshold: {low} lux)",
                0.85
            )
        elif value > high:
            return (
                "ANOMALY",
                "warning",
                f"☀️ Light level is high: {value} lux (threshold: {high} lux)",
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
