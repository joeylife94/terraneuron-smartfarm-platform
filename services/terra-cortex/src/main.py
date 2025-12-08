from fastapi import FastAPI
from contextlib import asynccontextmanager
import logging
from src.config import settings
from src.kafka_service import kafka_service

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작
    logger.info("🧠 Terra-Cortex AI Engine 시작...")
    kafka_service.start()
    yield
    # 종료
    logger.info("🛑 Terra-Cortex AI Engine 종료...")
    kafka_service.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="🧠 TerraNeuron AI 분석 엔진 - 센서 데이터 이상 탐지",
    lifespan=lifespan
)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "service": "terra-cortex",
        "version": settings.app_version,
        "status": "running",
        "description": "TerraNeuron AI Brain - Anomaly Detection Engine"
    }


@app.get("/health")
async def health():
    """헬스 체크"""
    return {
        "status": "healthy",
        "kafka_consumer": kafka_service.running,
        "input_topic": settings.kafka_input_topic,
        "output_topic": settings.kafka_output_topic
    }


@app.get("/config")
async def get_config():
    """현재 설정 조회"""
    return {
        "kafka_bootstrap_servers": settings.kafka_bootstrap_servers,
        "kafka_input_topic": settings.kafka_input_topic,
        "kafka_output_topic": settings.kafka_output_topic,
        "anomaly_threshold": settings.anomaly_threshold
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
