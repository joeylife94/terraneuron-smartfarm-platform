"""
Parquet Exporter
대규모 ML 학습용 Parquet 데이터셋 내보내기.
효율적인 컬럼 기반 스토리지, 빠른 분석 쿼리.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from src.models import CollectedSensorData
from src.exporters import BaseExporter

logger = logging.getLogger(__name__)


class ParquetExporter(BaseExporter):
    """Parquet 형식으로 대규모 ML 학습 데이터 내보내기"""

    @property
    def name(self) -> str:
        return "parquet_export"

    async def export(self, records: List[CollectedSensorData]) -> int:
        """Parquet 파일로 내보내기"""
        if not records:
            return 0

        output_dir = Path(self.config.get("output_dir", "./data/exports/parquet"))
        output_dir.mkdir(parents=True, exist_ok=True)
        compression = self.config.get("compression", "snappy")

        rows = [r.to_training_record() for r in records]
        df = pd.DataFrame(rows)

        # 센서 타입별 분할 저장 (ML 학습 시 편의)
        saved = 0
        for sensor_type, group_df in df.groupby("sensorType"):
            filepath = output_dir / f"sensor_{sensor_type}.parquet"

            if filepath.exists():
                existing = pd.read_parquet(filepath)
                group_df = pd.concat([existing, group_df], ignore_index=True)
                group_df.drop_duplicates(
                    subset=["sensorId", "timestamp"], keep="last", inplace=True,
                )

            group_df.to_parquet(filepath, compression=compression, index=False)
            saved += len(group_df)
            logger.debug(f"  💾 {filepath.name}: {len(group_df)} records")

        self._export_count += saved
        logger.info(f"💾 [parquet_export] Saved {saved} records to {output_dir}")
        return saved
