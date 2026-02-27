"""
JSONL Exporter
LLM 파인튜닝용 JSONL 데이터셋 내보내기.
Instruction-tuning 형식 (Alpaca / ShareGPT 호환).
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from src.models import CollectedSensorData
from src.exporters import BaseExporter

logger = logging.getLogger(__name__)


class JsonlExporter(BaseExporter):
    """
    JSONL 형식으로 LLM 파인튜닝 데이터 내보내기.
    On-device AI 학습에 직접 사용 가능.
    """

    @property
    def name(self) -> str:
        return "jsonl_export"

    async def export(self, records: List[CollectedSensorData]) -> int:
        """JSONL 파일로 내보내기"""
        if not records:
            return 0

        output_dir = Path(self.config.get("output_dir", "./data/exports/jsonl"))
        output_dir.mkdir(parents=True, exist_ok=True)
        fmt = self.config.get("format", "instruction")

        saved = 0

        if fmt == "instruction":
            saved = await self._export_instruction_format(records, output_dir)
        elif fmt == "raw":
            saved = await self._export_raw_format(records, output_dir)
        else:
            saved = await self._export_instruction_format(records, output_dir)

        self._export_count += saved
        logger.info(f"💾 [jsonl_export] Saved {saved} records to {output_dir}")
        return saved

    async def _export_instruction_format(
        self, records: List[CollectedSensorData], output_dir: Path,
    ) -> int:
        """
        Alpaca instruction-tuning 형식:
        {"instruction": "...", "input": "...", "output": "..."}
        """
        filepath = output_dir / "finetune_instructions.jsonl"
        count = 0

        with open(filepath, "a", encoding="utf-8") as f:
            for record in records:
                entry = record.to_finetune_instruction()
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                count += 1

        # Conversation 포맷도 생성 (ShareGPT 호환)
        conv_path = output_dir / "finetune_conversations.jsonl"
        with open(conv_path, "a", encoding="utf-8") as f:
            for record in records:
                instr = record.to_finetune_instruction()
                conv = {
                    "conversations": [
                        {
                            "from": "human",
                            "value": instr["instruction"] + "\n" + instr["input"],
                        },
                        {
                            "from": "gpt",
                            "value": instr["output"],
                        },
                    ]
                }
                f.write(json.dumps(conv, ensure_ascii=False) + "\n")

        return count

    async def _export_raw_format(
        self, records: List[CollectedSensorData], output_dir: Path,
    ) -> int:
        """전체 레코드 JSONL (ML 학습용)"""
        filepath = output_dir / "sensor_data_raw.jsonl"
        count = 0

        with open(filepath, "a", encoding="utf-8") as f:
            for record in records:
                entry = record.to_training_record()
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                count += 1

        return count
