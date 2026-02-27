"""
Terra Data Collector - Configuration Management
YAML 설정 파일 로드 및 환경 변수 오버라이드
"""
import os
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """애플리케이션 전체 설정"""

    # 농장 매핑
    farms: List[Dict[str, Any]] = Field(default_factory=list)

    # 제공자 설정
    providers: Dict[str, Any] = Field(default_factory=dict)

    # 내보내기 설정
    exporters: Dict[str, Any] = Field(default_factory=dict)

    # 태깅 설정
    tagging: Dict[str, Any] = Field(default_factory=lambda: {
        "source_label": "external",
        "provider_label": True,
        "quality_label": True,
    })

    # 스케줄러 설정
    scheduler: Dict[str, Any] = Field(default_factory=dict)

    # 로깅 설정
    logging: Dict[str, Any] = Field(default_factory=lambda: {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    })


def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    설정 파일 로드.
    우선순위: 환경 변수 > config.yaml > 기본값
    """
    if config_path is None:
        config_path = os.getenv(
            "TERRA_COLLECTOR_CONFIG",
            str(Path(__file__).parent.parent / "config.yaml"),
        )

    config_data: Dict[str, Any] = {}

    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

    # 환경 변수 오버라이드
    env_overrides = {
        "TERRA_SENSE_URL": ("exporters", "terra_bridge", "terra_sense_url"),
        "KAFKA_BOOTSTRAP_SERVERS": ("exporters", "kafka_bridge", "bootstrap_servers"),
        "COLLECTOR_LOG_LEVEL": ("logging", "level"),
    }

    for env_key, path in env_overrides.items():
        env_val = os.getenv(env_key)
        if env_val:
            _set_nested(config_data, path, env_val)

    return AppConfig(**config_data)


def _set_nested(d: dict, keys: tuple, value: Any):
    """중첩 딕셔너리에 값 설정"""
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value
