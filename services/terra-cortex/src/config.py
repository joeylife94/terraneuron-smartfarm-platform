from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """환경 변수 설정"""
    
    # Kafka 설정
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_input_topic: str = "raw-sensor-data"
    kafka_output_topic: str = "processed-insights"
    kafka_consumer_group: str = "terra-cortex-group"
    
    # FastAPI 설정
    app_name: str = "terra-cortex"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # AI 모델 설정
    anomaly_threshold: float = 0.8
    model_path: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
