"""
Weather Data Provider for Terra-Cortex
외부 기상 API에서 실시간 날씨 데이터를 비동기로 가져와 분석 파이프라인에 컨텍스트를 제공

지원 API:
  1순위: OpenWeatherMap (무료 tier: 1000 calls/day)
  2순위: 기상청 공공 API (한국 농업 특화)
  폴백: 캐시된 이전 데이터 or None

캐시 전략:
  - 날씨는 10분 단위로 갱신 (센서는 초 단위이므로 불필요한 API 콜 방지)
  - TTL 기반 in-memory 캐시
"""
import asyncio
import os
import logging
import time
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Configuration
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_PROVIDER = os.getenv("WEATHER_PROVIDER", "openweathermap")  # openweathermap | kma
WEATHER_LAT = float(os.getenv("WEATHER_LAT", "35.1796"))  # Default: 대전 (한국 중부)
WEATHER_LON = float(os.getenv("WEATHER_LON", "129.0756"))  # Default: 부산
WEATHER_CACHE_TTL = int(os.getenv("WEATHER_CACHE_TTL", "600"))  # 10분


@dataclass
class WeatherData:
    """날씨 데이터 모델"""
    temperature: float          # 외기 온도 (°C)
    humidity: float             # 외기 습도 (%)
    description: str            # 날씨 설명 (e.g., "맑음", "흐림")
    wind_speed: float           # 풍속 (m/s)
    rain_1h: float = 0.0       # 1시간 강수량 (mm)
    clouds: int = 0             # 구름양 (%)
    uvi: Optional[float] = None # UV Index
    feels_like: Optional[float] = None  # 체감 온도 (°C)
    forecast_temp_max: Optional[float] = None  # 오늘 최고 기온 예보
    forecast_temp_min: Optional[float] = None  # 오늘 최저 기온 예보
    sunrise: Optional[str] = None   # 일출 시각
    sunset: Optional[str] = None    # 일몰 시각
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "openweathermap"

    def to_context_string(self) -> str:
        """분석 파이프라인용 컨텍스트 문자열 생성"""
        parts = [
            f"외기 온도: {self.temperature}°C",
            f"외기 습도: {self.humidity}%",
            f"날씨: {self.description}",
            f"풍속: {self.wind_speed}m/s",
            f"구름: {self.clouds}%",
        ]
        if self.rain_1h > 0:
            parts.append(f"1시간 강수량: {self.rain_1h}mm")
        if self.feels_like is not None:
            parts.append(f"체감 온도: {self.feels_like}°C")
        if self.forecast_temp_max is not None:
            parts.append(f"오늘 최고/최저: {self.forecast_temp_max}°C / {self.forecast_temp_min}°C")
        if self.sunrise:
            parts.append(f"일출/일몰: {self.sunrise} / {self.sunset}")
        return " | ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        """JSON 직렬화용 딕셔너리"""
        return {
            "temperature": self.temperature,
            "humidity": self.humidity,
            "description": self.description,
            "wind_speed": self.wind_speed,
            "rain_1h": self.rain_1h,
            "clouds": self.clouds,
            "uvi": self.uvi,
            "feels_like": self.feels_like,
            "forecast_temp_max": self.forecast_temp_max,
            "forecast_temp_min": self.forecast_temp_min,
            "sunrise": self.sunrise,
            "sunset": self.sunset,
            "fetched_at": self.fetched_at.isoformat(),
            "source": self.source,
        }


class WeatherProvider:
    """
    비동기 날씨 데이터 제공자 (TTL 캐시 내장)
    """

    def __init__(self):
        self.api_key = WEATHER_API_KEY
        self.provider = WEATHER_PROVIDER
        self.lat = WEATHER_LAT
        self.lon = WEATHER_LON
        self.cache_ttl = WEATHER_CACHE_TTL
        self.enabled = bool(self.api_key)

        # 캐시
        self._cache: Optional[WeatherData] = None
        self._cache_time: float = 0.0

        # 통계
        self.fetch_count = 0
        self.cache_hit_count = 0
        self.error_count = 0

        if self.enabled:
            logger.info(
                f"✅ WeatherProvider initialized: provider={self.provider}, "
                f"location=({self.lat}, {self.lon}), cache_ttl={self.cache_ttl}s"
            )
        else:
            logger.warning("⚠️ WeatherProvider disabled (WEATHER_API_KEY not set)")

    async def get_weather(self) -> Optional[WeatherData]:
        """
        현재 날씨 데이터 반환 (캐시 우선)
        
        Returns:
            WeatherData or None (API 비활성화/오류 시)
        """
        if not self.enabled:
            return None

        # 캐시 유효성 확인
        now = time.time()
        if self._cache and (now - self._cache_time) < self.cache_ttl:
            self.cache_hit_count += 1
            logger.debug(f"🔄 Weather cache hit (age: {int(now - self._cache_time)}s)")
            return self._cache

        # API 호출
        try:
            if self.provider == "openweathermap":
                weather = await self._fetch_openweathermap()
            elif self.provider == "kma":
                weather = await self._fetch_kma()
            else:
                logger.error(f"Unknown weather provider: {self.provider}")
                return self._cache  # 폴백: 이전 캐시

            if weather:
                self._cache = weather
                self._cache_time = now
                self.fetch_count += 1
                logger.info(
                    f"🌤️ Weather updated: {weather.temperature}°C, "
                    f"{weather.humidity}%, {weather.description}"
                )
            return weather

        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ Weather fetch error: {e}")
            return self._cache  # 폴백: 이전 캐시

    async def _fetch_openweathermap(self) -> Optional[WeatherData]:
        """OpenWeatherMap API 호출 (Current Weather + One Call 3.0 폴백)"""
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": self.lat,
            "lon": self.lon,
            "appid": self.api_key,
            "units": "metric",
            "lang": "kr",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        main = data.get("main", {})
        wind = data.get("wind", {})
        rain = data.get("rain", {})
        clouds = data.get("clouds", {})
        weather_desc = data.get("weather", [{}])[0].get("description", "N/A")
        sys_info = data.get("sys", {})

        sunrise_ts = sys_info.get("sunrise")
        sunset_ts = sys_info.get("sunset")
        sunrise_str = datetime.fromtimestamp(sunrise_ts, tz=timezone.utc).strftime("%H:%M") if sunrise_ts else None
        sunset_str = datetime.fromtimestamp(sunset_ts, tz=timezone.utc).strftime("%H:%M") if sunset_ts else None

        return WeatherData(
            temperature=main.get("temp", 0.0),
            humidity=main.get("humidity", 0.0),
            description=weather_desc,
            wind_speed=wind.get("speed", 0.0),
            rain_1h=rain.get("1h", 0.0),
            clouds=clouds.get("all", 0),
            feels_like=main.get("feels_like"),
            forecast_temp_max=main.get("temp_max"),
            forecast_temp_min=main.get("temp_min"),
            sunrise=sunrise_str,
            sunset=sunset_str,
            source="openweathermap",
        )

    async def _fetch_kma(self) -> Optional[WeatherData]:
        """
        기상청 공공 API 폴백 (추후 구현)
        https://data.kma.go.kr 에서 API 키 발급 필요
        """
        logger.warning("기상청 API는 아직 미구현입니다. OpenWeatherMap을 사용하세요.")
        return None

    def get_stats(self) -> Dict[str, Any]:
        """통계 반환"""
        return {
            "enabled": self.enabled,
            "provider": self.provider,
            "location": {"lat": self.lat, "lon": self.lon},
            "cache_ttl_seconds": self.cache_ttl,
            "total_fetches": self.fetch_count,
            "cache_hits": self.cache_hit_count,
            "errors": self.error_count,
            "last_weather": self._cache.to_dict() if self._cache else None,
        }


# Singleton instance
_weather_provider: Optional[WeatherProvider] = None


def get_weather_provider() -> WeatherProvider:
    """싱글톤 WeatherProvider 반환"""
    global _weather_provider
    if _weather_provider is None:
        _weather_provider = WeatherProvider()
    return _weather_provider
