"""
CSV Exporter
AI 학습용 CSV 데이터셋 내보내기.
pandas DataFrame으로 변환 후 일별/주별/월별 분할 저장.
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from src.models import CollectedSensorData
from src.exporters import BaseExporter

logger = logging.getLogger(__name__)


class CsvExporter(BaseExporter):
    """CSV 형식으로 AI 학습 데이터셋 내보내기"""

    @property
    def name(self) -> str:
        return "csv_export"

    async def export(self, records: List[CollectedSensorData]) -> int:
        """CSV 파일로 내보내기"""
        if not records:
            return 0

        output_dir = Path(self.config.get("output_dir", "./data/exports/csv"))
        output_dir.mkdir(parents=True, exist_ok=True)
        include_metadata = self.config.get("include_metadata", True)

        # DataFrame 변환
        if include_metadata:
            rows = [r.to_training_record() for r in records]
        else:
            rows = [r.to_terra_sense_payload() for r in records]

        df = pd.DataFrame(rows)

        # 타임스탬프 파싱
        df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

        split_by = self.config.get("split_by", "daily")
        saved = 0

        if split_by == "daily":
            df["_group"] = df["_ts"].dt.strftime("%Y-%m-%d")
        elif split_by == "weekly":
            df["_group"] = df["_ts"].dt.strftime("%Y-W%U")
        elif split_by == "monthly":
            df["_group"] = df["_ts"].dt.strftime("%Y-%m")
        else:
            df["_group"] = "all"

        for group_key, group_df in df.groupby("_group"):
            filename = f"sensor_data_{group_key}.csv"
            filepath = output_dir / filename

            # 내부 칼럼 제거
            export_df = group_df.drop(columns=["_ts", "_group"], errors="ignore")

            # 기존 파일이 있으면 append
            if filepath.exists():
                existing = pd.read_csv(filepath)
                export_df = pd.concat([existing, export_df], ignore_index=True)
                export_df.drop_duplicates(
                    subset=["sensorId", "timestamp"], keep="last", inplace=True,
                )

            export_df.to_csv(filepath, index=False, encoding="utf-8")
            saved += len(group_df)
            logger.debug(f"  💾 {filepath.name}: {len(group_df)} records")

        self._export_count += saved
        logger.info(f"💾 [csv_export] Saved {saved} records to {output_dir}")
        return saved
