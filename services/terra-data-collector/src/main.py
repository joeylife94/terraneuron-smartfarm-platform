"""
Terra Data Collector - FastAPI Service
HTTP API 서버 + 스케줄러 통합 실행
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, Query, HTTPException

from src.config import load_config
from src.collector import Collector
from src.scheduler import CollectionScheduler

# Logging
log_level = os.getenv("COLLECTOR_LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global instances
collector: Optional[Collector] = None
scheduler: Optional[CollectionScheduler] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클"""
    global collector, scheduler

    logger.info("🌱 Terra Data Collector starting...")

    # 설정 로드
    config = load_config()
    logger.info(f"  📋 Loaded config: {len(config.farms)} farms, "
                f"{len(config.providers)} providers")

    # Collector 초기화
    collector = Collector(config)

    # Scheduler 시작 (설정에서 활성화된 경우)
    if config.scheduler.get("enabled", False):
        scheduler = CollectionScheduler(collector, config.scheduler)
        scheduler.start()
    else:
        logger.info("  ⏭️ Scheduler disabled")

    logger.info("✅ Terra Data Collector ready!")
    yield

    # 종료
    logger.info("🛑 Terra Data Collector shutting down...")
    if scheduler:
        scheduler.stop()


app = FastAPI(
    title="Terra Data Collector",
    version="1.0.0",
    description=(
        "🌱 외부 공개 데이터 수집 서비스\n\n"
        "무료 공개 API에서 농업 관련 데이터를 수집하여 "
        "TerraNeuron 파이프라인에 주입하거나 AI 학습 데이터로 내보냅니다."
    ),
    lifespan=lifespan,
)


# ============ API Endpoints ============

@app.get("/")
async def root() -> Dict[str, Any]:
    """서비스 정보"""
    return {
        "service": "terra-data-collector",
        "version": "1.0.0",
        "description": "External agricultural data collection service",
        "status": "running",
        "stats": collector.get_stats() if collector else {},
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    """헬스체크"""
    return {
        "status": "healthy",
        "collector_ready": collector is not None,
        "scheduler_running": scheduler is not None,
    }


@app.post("/collect/realtime")
async def collect_realtime(
    providers: Optional[List[str]] = Query(default=None, description="사용할 Provider 목록"),
    exporters: Optional[List[str]] = Query(default=None, description="사용할 Exporter 목록"),
) -> Dict[str, Any]:
    """
    실시간 데이터 수집 실행.
    현재 시점의 외부 데이터를 수집하여 지정된 Exporter로 내보냅니다.
    """
    if not collector:
        raise HTTPException(500, "Collector not initialized")

    summary = await collector.collect_and_export(
        provider_names=providers,
        exporter_names=exporters,
        historical=False,
    )
    return summary.model_dump(mode="json")


@app.post("/collect/historical")
async def collect_historical(
    providers: Optional[List[str]] = Query(default=None),
    exporters: Optional[List[str]] = Query(default=None),
    start_date: Optional[str] = Query(default=None, description="시작일 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="종료일 (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    """
    과거 데이터 수집 실행.
    AI 학습용 대량 데이터를 수집합니다.
    """
    if not collector:
        raise HTTPException(500, "Collector not initialized")

    summary = await collector.collect_and_export(
        provider_names=providers,
        exporter_names=exporters,
        historical=True,
        start_date=start_date,
        end_date=end_date,
    )
    return summary.model_dump(mode="json")


@app.get("/stats")
async def stats() -> Dict[str, Any]:
    """수집 통계"""
    result: Dict[str, Any] = {}
    if collector:
        result["collector"] = collector.get_stats()
    if scheduler:
        result["scheduler"] = {"jobs": scheduler.get_jobs()}
    return result


@app.get("/providers")
async def list_providers() -> Dict[str, Any]:
    """활성화된 Provider 목록"""
    if not collector:
        return {"providers": []}
    return {
        "providers": [
            p.get_stats() for p in collector.providers.values()
        ]
    }


@app.get("/exporters")
async def list_exporters() -> Dict[str, Any]:
    """활성화된 Exporter 목록"""
    if not collector:
        return {"exporters": []}
    return {
        "exporters": [
            e.get_stats() for e in collector.exporters.values()
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8083)
