"""
Time Series Analyzer for Terra-Cortex
InfluxDB Flux 쿼리를 통한 센서 데이터 추세 분석

기능:
  1. 이동 평균 (Moving Average) 이상 탐지
  2. 최근 N시간 추세 분석 (상승/하강/안정)
  3. 일/주/월 패턴 통계
  4. 급변 감지 (Rate of Change)
  5. 예측값 추정 (선형 회귀)

아키텍처:
  - InfluxDB 2.7 Flux 쿼리 직접 호출
  - 결과는 TrendContext로 패키징 → local_analyzer / cloud_advisor에 전달
  - TTL 캐시로 동일 farmId+sensorType 반복 조회 방지
"""
import asyncio
import logging
import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple

import httpx

logger = logging.getLogger(__name__)

# Configuration
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "terra-token-2025")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "terraneuron")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor_data")
TREND_CACHE_TTL = int(os.getenv("TREND_CACHE_TTL", "120"))  # 2분 (센서 데이터 빠름)
TREND_WINDOW = os.getenv("TREND_WINDOW", "1h")  # 기본 분석 윈도우


@dataclass
class TrendPoint:
    """시계열 데이터 포인트"""
    time: datetime
    value: float


@dataclass
class TrendStats:
    """추세 통계 요약"""
    mean: float
    std: float
    min_val: float
    max_val: float
    count: int
    latest: float
    direction: str  # "rising", "falling", "stable"
    rate_of_change: float  # 단위시간당 변화율
    moving_avg: float  # 이동 평균
    deviation_from_ma: float  # 현재값 - 이동평균 (양수: 평균 이상, 음수: 평균 이하)
    is_spike: bool  # 급변 감지 (현재값이 2σ 이상 벗어남)
    predicted_next: Optional[float] = None  # 선형 회귀 예측값 (10분 후)
    period: str = "1h"  # 분석 기간


@dataclass
class DailyPattern:
    """일간 패턴 통계"""
    hour: int
    avg_value: float
    min_value: float
    max_value: float


@dataclass
class TrendContext:
    """분석 파이프라인에 전달되는 추세 컨텍스트"""
    farm_id: str
    sensor_type: str
    has_data: bool
    stats: Optional[TrendStats] = None
    recent_points: List[TrendPoint] = field(default_factory=list)
    daily_pattern: List[DailyPattern] = field(default_factory=list)
    message: Optional[str] = None

    def to_context_string(self) -> str:
        """분석 파이프라인용 요약 문자열"""
        if not self.has_data or not self.stats:
            return f"{self.farm_id}/{self.sensor_type}: 시계열 데이터 없음"

        s = self.stats
        parts = [
            f"최근 {s.period}: 평균={s.mean:.1f}, 표준편차={s.std:.1f}",
            f"범위={s.min_val:.1f}~{s.max_val:.1f}, 최신={s.latest:.1f}",
            f"추세={s.direction}(변화율={s.rate_of_change:+.2f}/h)",
            f"이동평균={s.moving_avg:.1f}, 편차={s.deviation_from_ma:+.1f}",
        ]
        if s.is_spike:
            parts.append("⚠️ 급변 감지")
        if s.predicted_next is not None:
            parts.append(f"10분후 예측={s.predicted_next:.1f}")
        return " | ".join(parts)


class TimeSeriesAnalyzer:
    """
    InfluxDB Flux 쿼리 기반 시계열 분석기
    """

    def __init__(self):
        self.url = INFLUXDB_URL
        self.token = INFLUXDB_TOKEN
        self.org = INFLUXDB_ORG
        self.bucket = INFLUXDB_BUCKET
        self.window = TREND_WINDOW
        self.cache_ttl = TREND_CACHE_TTL
        self.enabled = bool(self.token)

        # (farmId, sensorType) → (TrendContext, fetch_time)
        self._cache: Dict[Tuple[str, str], Tuple[TrendContext, float]] = {}

        # 통계
        self.query_count = 0
        self.cache_hit_count = 0
        self.error_count = 0

        logger.info(
            f"✅ TimeSeriesAnalyzer initialized: "
            f"influxdb={self.url}, bucket={self.bucket}, window={self.window}, cache_ttl={self.cache_ttl}s"
        )

    def get_config(self) -> dict:
        """Return configuration and stats for /info endpoint"""
        return {
            "influxdb_url": self.url,
            "bucket": self.bucket,
            "org": self.org,
            "window": self.window,
            "cache_ttl": self.cache_ttl,
            "enabled": self.enabled,
            "stats": {
                "query_count": self.query_count,
                "cache_hit_count": self.cache_hit_count,
                "error_count": self.error_count,
            }
        }

    async def get_trend_context(
        self, farm_id: str, sensor_type: str, window: str = None
    ) -> Optional[TrendContext]:
        """
        특정 farmId/sensorType의 최근 추세 컨텍스트 조회

        Args:
            farm_id: 농장 식별자
            sensor_type: 센서 유형 (temperature, humidity, co2, ...)
            window: 분석 윈도우 (기본: 1h)

        Returns:
            TrendContext or None
        """
        w = window or self.window
        cache_key = (farm_id, sensor_type)

        # 캐시 확인
        now = time.time()
        if cache_key in self._cache:
            ctx, cached_at = self._cache[cache_key]
            if (now - cached_at) < self.cache_ttl:
                self.cache_hit_count += 1
                return ctx

        try:
            self.query_count += 1

            # InfluxDB Flux 쿼리: 최근 윈도우의 데이터 조회
            points = await self._query_recent_data(farm_id, sensor_type, w)

            if not points or len(points) < 2:
                ctx = TrendContext(
                    farm_id=farm_id,
                    sensor_type=sensor_type,
                    has_data=False,
                    message=f"데이터 부족 (최근 {w}: {len(points) if points else 0}건)",
                )
                self._cache[cache_key] = (ctx, now)
                return ctx

            # 통계 계산
            stats = self._compute_stats(points, w)

            # 일간 패턴 (24시간 데이터가 충분한 경우)
            daily = []
            if w in ("24h", "1d", "7d", "30d") and len(points) > 24:
                daily = self._compute_daily_pattern(points)

            ctx = TrendContext(
                farm_id=farm_id,
                sensor_type=sensor_type,
                has_data=True,
                stats=stats,
                recent_points=points[-10:],  # 최근 10개 포인트만 보존
                daily_pattern=daily,
            )
            self._cache[cache_key] = (ctx, now)

            logger.info(
                f"📈 Trend context: {farm_id}/{sensor_type} "
                f"→ {stats.direction} (μ={stats.mean:.1f}, σ={stats.std:.1f}, "
                f"spike={stats.is_spike})"
            )
            return ctx

        except Exception as e:
            self.error_count += 1
            logger.error(f"❌ TimeSeries query error for {farm_id}/{sensor_type}: {e}")
            # 이전 캐시가 있으면 만료되어도 반환 (graceful degradation)
            if cache_key in self._cache:
                return self._cache[cache_key][0]
            return TrendContext(
                farm_id=farm_id,
                sensor_type=sensor_type,
                has_data=False,
                message=f"InfluxDB 쿼리 오류: {str(e)[:100]}",
            )

    async def _query_recent_data(
        self, farm_id: str, sensor_type: str, window: str
    ) -> List[TrendPoint]:
        """InfluxDB Flux 쿼리로 최근 데이터 조회"""
        flux_query = f'''
from(bucket: "{self.bucket}")
  |> range(start: -{window})
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["farmId"] == "{farm_id}")
  |> filter(fn: (r) => r["sensorType"] == "{sensor_type}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> sort(columns: ["_time"])
'''
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/vnd.flux",
            "Accept": "application/csv",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{self.url}/api/v2/query?org={self.org}",
                headers=headers,
                content=flux_query,
            )
            response.raise_for_status()

        return self._parse_csv_response(response.text)

    async def query_daily_stats(
        self, farm_id: str, sensor_type: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """일별 통계 (평균, 최소, 최대) — REST API용"""
        flux_query = f'''
from(bucket: "{self.bucket}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["farmId"] == "{farm_id}")
  |> filter(fn: (r) => r["sensorType"] == "{sensor_type}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
  |> yield(name: "daily_mean")
'''
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/vnd.flux",
            "Accept": "application/csv",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/api/v2/query?org={self.org}",
                    headers=headers,
                    content=flux_query,
                )
                response.raise_for_status()

            points = self._parse_csv_response(response.text)
            return [
                {"date": p.time.strftime("%Y-%m-%d"), "mean": round(p.value, 2)}
                for p in points
            ]
        except Exception as e:
            logger.error(f"❌ Daily stats query error: {e}")
            return []

    async def query_hourly_pattern(
        self, farm_id: str, sensor_type: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """시간대별 평균 패턴 (최근 N일) — REST API용"""
        flux_query = f'''
import "date"

from(bucket: "{self.bucket}")
  |> range(start: -{days}d)
  |> filter(fn: (r) => r["_measurement"] == "sensor_data")
  |> filter(fn: (r) => r["farmId"] == "{farm_id}")
  |> filter(fn: (r) => r["sensorType"] == "{sensor_type}")
  |> filter(fn: (r) => r["_field"] == "value")
  |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
  |> map(fn: (r) => ({{ r with hour: date.hour(t: r._time) }}))
  |> group(columns: ["hour"])
  |> mean(column: "_value")
'''
        headers = {
            "Authorization": f"Token {self.token}",
            "Content-Type": "application/vnd.flux",
            "Accept": "application/csv",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.url}/api/v2/query?org={self.org}",
                    headers=headers,
                    content=flux_query,
                )
                response.raise_for_status()

            points = self._parse_csv_response(response.text)
            return [
                {"hour": i, "avg": round(p.value, 2)}
                for i, p in enumerate(points)
            ]
        except Exception as e:
            logger.error(f"❌ Hourly pattern query error: {e}")
            return []

    def _parse_csv_response(self, csv_text: str) -> List[TrendPoint]:
        """InfluxDB CSV 응답을 TrendPoint 리스트로 파싱"""
        points = []
        lines = csv_text.strip().split("\n")
        if len(lines) < 2:
            return points

        # 헤더 파싱
        header = None
        for line in lines:
            if line.startswith("#") or line.strip() == "":
                continue
            if header is None:
                header = line.split(",")
                continue

            cols = line.split(",")
            if len(cols) < len(header):
                continue

            col_map = dict(zip(header, cols))

            # _time 과 _value 추출
            time_str = col_map.get("_time", "")
            value_str = col_map.get("_value", "")

            if not time_str or not value_str:
                continue

            try:
                # ISO 8601 파싱
                t = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                v = float(value_str)
                points.append(TrendPoint(time=t, value=v))
            except (ValueError, TypeError):
                continue

        return points

    def _compute_stats(self, points: List[TrendPoint], window: str) -> TrendStats:
        """추세 통계 계산"""
        values = [p.value for p in points]
        n = len(values)

        mean_val = sum(values) / n
        std_val = math.sqrt(sum((v - mean_val) ** 2 for v in values) / n) if n > 1 else 0.0
        min_val = min(values)
        max_val = max(values)
        latest = values[-1]

        # 이동 평균 (최근 절반)
        ma_window = max(n // 2, 3)
        ma_values = values[-ma_window:]
        moving_avg = sum(ma_values) / len(ma_values)

        # 현재값과 이동평균의 편차
        deviation = latest - moving_avg

        # 급변 감지: 2σ 이상 벗어남
        is_spike = abs(deviation) > 2 * std_val if std_val > 0 else False

        # 추세 방향: 전반부 평균 vs 후반부 평균
        half = n // 2
        first_half_mean = sum(values[:half]) / half if half > 0 else mean_val
        second_half_mean = sum(values[half:]) / (n - half) if (n - half) > 0 else mean_val
        diff = second_half_mean - first_half_mean

        if abs(diff) < std_val * 0.3:
            direction = "stable"
        elif diff > 0:
            direction = "rising"
        else:
            direction = "falling"

        # 변화율: (마지막 - 처음) / 시간차(시간)
        time_span_hours = (
            (points[-1].time - points[0].time).total_seconds() / 3600.0
        )
        rate_of_change = (
            (values[-1] - values[0]) / time_span_hours
            if time_span_hours > 0
            else 0.0
        )

        # 선형 회귀 예측 (10분 후)
        predicted = self._linear_predict(points, minutes_ahead=10)

        return TrendStats(
            mean=round(mean_val, 2),
            std=round(std_val, 2),
            min_val=round(min_val, 2),
            max_val=round(max_val, 2),
            count=n,
            latest=round(latest, 2),
            direction=direction,
            rate_of_change=round(rate_of_change, 3),
            moving_avg=round(moving_avg, 2),
            deviation_from_ma=round(deviation, 2),
            is_spike=is_spike,
            predicted_next=round(predicted, 2) if predicted is not None else None,
            period=window,
        )

    def _linear_predict(
        self, points: List[TrendPoint], minutes_ahead: int = 10
    ) -> Optional[float]:
        """단순 선형 회귀로 N분 후 예측"""
        if len(points) < 5:
            return None

        # 최근 데이터로만 회귀 (최대 30개)
        recent = points[-30:]
        n = len(recent)
        base_time = recent[0].time.timestamp()

        xs = [(p.time.timestamp() - base_time) / 60.0 for p in recent]  # 분 단위
        ys = [p.value for p in recent]

        x_mean = sum(xs) / n
        y_mean = sum(ys) / n

        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
        denominator = sum((x - x_mean) ** 2 for x in xs)

        if denominator == 0:
            return None

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # N분 후 예측
        target_x = xs[-1] + minutes_ahead
        return slope * target_x + intercept

    def _compute_daily_pattern(self, points: List[TrendPoint]) -> List[DailyPattern]:
        """시간대별 통계 계산"""
        hour_data: Dict[int, List[float]] = {}
        for p in points:
            h = p.time.hour
            hour_data.setdefault(h, []).append(p.value)

        patterns = []
        for h in sorted(hour_data.keys()):
            vals = hour_data[h]
            patterns.append(
                DailyPattern(
                    hour=h,
                    avg_value=round(sum(vals) / len(vals), 2),
                    min_value=round(min(vals), 2),
                    max_value=round(max(vals), 2),
                )
            )
        return patterns

    def get_stats(self) -> Dict[str, Any]:
        return {
            "provider": "influxdb",
            "url": self.url,
            "bucket": self.bucket,
            "window": self.window,
            "enabled": self.enabled,
            "total_queries": self.query_count,
            "cache_hits": self.cache_hit_count,
            "errors": self.error_count,
            "cached_keys": len(self._cache),
        }


# Singleton factory
_analyzer: Optional[TimeSeriesAnalyzer] = None


def get_timeseries_analyzer() -> TimeSeriesAnalyzer:
    """싱글톤 TimeSeriesAnalyzer 반환"""
    global _analyzer
    if _analyzer is None:
        _analyzer = TimeSeriesAnalyzer()
    return _analyzer
