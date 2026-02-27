"""
Knowledge Collector — Automated Knowledge Accumulation Pipeline
Collects operational insights, anomaly patterns, and action outcomes
to continuously enrich the RAG knowledge base (ChromaDB).

Pipeline:
  1. Insight Patterns  — Aggregate anomaly patterns by sensor/farm/season
  2. Action Outcomes   — Learn from approved action plans and their results
  3. Weather Correlations — Region-specific weather ↔ sensor correlations
  4. Auto-Embedding    — Periodically embed collected knowledge into ChromaDB
"""
import asyncio
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────
TERRA_OPS_URL = os.getenv("TERRA_OPS_URL", "http://terra-ops:8080")
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "/app/data/knowledge_base")
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "/app/data/chroma_db")
COLLECTION_INTERVAL_MIN = int(os.getenv("KNOWLEDGE_COLLECT_INTERVAL", "60"))  # minutes
EMBED_BATCH_SIZE = int(os.getenv("KNOWLEDGE_EMBED_BATCH_SIZE", "20"))


@dataclass
class KnowledgeEntry:
    """A single knowledge document to be embedded into RAG"""
    entry_id: str
    source: str                   # "insight_pattern" | "action_outcome" | "weather_correlation" | "manual"
    category: str                 # "anomaly", "best_practice", "seasonal", "crop_specific"
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    embedded: bool = False

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


@dataclass
class InsightAccumulator:
    """Accumulates insight patterns over time for knowledge extraction"""
    anomaly_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    # key: "farmId:sensorType:severity"
    anomaly_messages: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    normal_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_reset: str = ""
    total_processed: int = 0

    def __post_init__(self):
        if not self.last_reset:
            self.last_reset = datetime.now(timezone.utc).isoformat()


class KnowledgeCollector:
    """
    Automated knowledge accumulation engine.
    Collects patterns from operational data and enriches RAG knowledge base.
    """

    def __init__(self):
        self.knowledge_path = Path(KNOWLEDGE_BASE_PATH)
        self.knowledge_path.mkdir(parents=True, exist_ok=True)
        self.generated_path = self.knowledge_path / "generated"
        self.generated_path.mkdir(parents=True, exist_ok=True)

        self.entries: List[KnowledgeEntry] = []
        self.accumulator = InsightAccumulator()
        self._http_client: Optional[httpx.AsyncClient] = None
        self._embed_fn = None
        self._vector_db = None
        self._collection_task: Optional[asyncio.Task] = None

        self.stats = {
            "total_entries": 0,
            "embedded_entries": 0,
            "insight_patterns_collected": 0,
            "action_outcomes_collected": 0,
            "weather_correlations_collected": 0,
            "last_collection": None,
            "last_embedding": None,
            "auto_collect_running": False,
        }

        logger.info("📚 KnowledgeCollector initialized")
        logger.info(f"   Knowledge base: {self.knowledge_path}")
        logger.info(f"   Collection interval: {COLLECTION_INTERVAL_MIN} min")

    # ─── HTTP Client ─────────────────────────────────────────────────

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0)
        return self._http_client

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass

    # ─── 1. Insight Pattern Accumulation ─────────────────────────────

    def accumulate_insight(self, insight_data: Dict[str, Any]):
        """
        Called for each processed insight. Accumulates patterns.
        This is called from the Kafka consumer loop in main.py.
        """
        farm_id = insight_data.get("farmId", "unknown")
        sensor_type = insight_data.get("sensorType", "unknown")
        status = insight_data.get("status", "NORMAL")
        severity = insight_data.get("severity", "info")
        message = insight_data.get("message", "")

        key = f"{farm_id}:{sensor_type}:{severity}"
        self.accumulator.total_processed += 1

        if status == "ANOMALY":
            self.accumulator.anomaly_counts[key] += 1
            msgs = self.accumulator.anomaly_messages[key]
            if len(msgs) < 10:  # Keep last 10 messages per key
                msgs.append(message)
        else:
            self.accumulator.normal_counts[key] += 1

    def extract_insight_patterns(self) -> List[KnowledgeEntry]:
        """
        Analyze accumulated insights and extract recurring patterns
        as knowledge entries.
        """
        entries: List[KnowledgeEntry] = []
        now = datetime.now(timezone.utc)

        for key, count in self.accumulator.anomaly_counts.items():
            if count < 3:  # Only extract if pattern occurs 3+ times
                continue

            farm_id, sensor_type, severity = key.split(":", 2)
            messages = self.accumulator.anomaly_messages.get(key, [])
            unique_msgs = list(set(messages))[:5]

            # Build knowledge document
            content = (
                f"## 반복 이상 패턴: {sensor_type} ({severity})\n\n"
                f"- 농장: {farm_id}\n"
                f"- 센서: {sensor_type}\n"
                f"- 심각도: {severity}\n"
                f"- 발생 횟수: {count}회\n"
                f"- 수집 기간: {self.accumulator.last_reset[:10]} ~ {now.isoformat()[:10]}\n\n"
                f"### 주요 메시지\n"
            )
            for msg in unique_msgs:
                content += f"- {msg}\n"

            content += (
                f"\n### 권장 대응\n"
                f"이 패턴은 {farm_id} 농장의 {sensor_type} 센서에서 반복적으로 발생합니다. "
                f"근본 원인 분석과 예방 조치를 검토하십시오. "
                f"환경 제어 장비의 캘리브레이션 또는 임계값 조정이 필요할 수 있습니다.\n"
            )

            entry_id = f"insight-{farm_id}-{sensor_type}-{severity}-{now.strftime('%Y%m%d')}"
            entries.append(KnowledgeEntry(
                entry_id=entry_id,
                source="insight_pattern",
                category="anomaly",
                title=f"반복 이상 패턴: {farm_id} {sensor_type} ({severity}) - {count}회",
                content=content,
                metadata={
                    "farm_id": farm_id,
                    "sensor_type": sensor_type,
                    "severity": severity,
                    "count": count,
                    "period_start": self.accumulator.last_reset,
                    "period_end": now.isoformat(),
                },
            ))

        self.stats["insight_patterns_collected"] += len(entries)
        return entries

    # ─── 2. Action Outcome Learning ──────────────────────────────────

    async def collect_action_outcomes(self) -> List[KnowledgeEntry]:
        """
        Fetch completed/executed action plans from terra-ops
        and extract lessons learned.
        """
        entries: List[KnowledgeEntry] = []
        try:
            client = await self._get_client()

            # Fetch action statistics
            stats_resp = await client.get(f"{TERRA_OPS_URL}/api/actions/statistics")
            if stats_resp.status_code != 200:
                logger.warning(f"⚠️ Failed to fetch action stats: {stats_resp.status_code}")
                return entries

            action_stats = stats_resp.json()
            executed = action_stats.get("executed", 0)
            rejected = action_stats.get("rejected", 0)
            failed = action_stats.get("failed", 0)
            total = executed + rejected + failed

            if total == 0:
                return entries

            # Generate action outcome knowledge
            now = datetime.now(timezone.utc)
            success_rate = (executed / total * 100) if total > 0 else 0

            content = (
                f"## 제어 액션 실행 결과 요약\n\n"
                f"- 수집일: {now.strftime('%Y-%m-%d')}\n"
                f"- 총 처리: {total}건\n"
                f"- 실행 성공: {executed}건 ({success_rate:.1f}%)\n"
                f"- 거부됨: {rejected}건\n"
                f"- 실패: {failed}건\n\n"
            )

            if success_rate >= 80:
                content += (
                    "### 분석\n"
                    "제어 액션의 성공률이 높습니다. 현재 안전 검증 로직과 액추에이터 매핑이 "
                    "효과적으로 작동하고 있습니다.\n"
                )
            elif success_rate >= 50:
                content += (
                    "### 분석\n"
                    "제어 액션 성공률이 보통입니다. 실패 원인을 분석하여 "
                    "안전 조건 또는 디바이스 설정을 재검토할 필요가 있습니다.\n"
                )
            else:
                content += (
                    "### 분석\n"
                    "제어 액션 성공률이 낮습니다 (50% 미만). 긴급히 "
                    "MQTT 연결, 디바이스 상태, 안전 검증 로직을 점검하십시오.\n"
                )

            if rejected > 0:
                content += (
                    f"\n### 거부 패턴\n"
                    f"총 {rejected}건이 거부되었습니다. 거부 사유를 분석하여 "
                    f"AI 액션 생성 로직을 개선하십시오.\n"
                )

            entry_id = f"action-outcome-{now.strftime('%Y%m%d')}"
            entries.append(KnowledgeEntry(
                entry_id=entry_id,
                source="action_outcome",
                category="best_practice",
                title=f"제어 액션 결과 요약 ({now.strftime('%Y-%m-%d')}): 성공률 {success_rate:.1f}%",
                content=content,
                metadata={
                    "executed": executed,
                    "rejected": rejected,
                    "failed": failed,
                    "success_rate": success_rate,
                    "date": now.isoformat(),
                },
            ))

            self.stats["action_outcomes_collected"] += len(entries)
            logger.info(f"📋 Collected {len(entries)} action outcome entries")

        except Exception as e:
            logger.warning(f"⚠️ Action outcome collection failed: {e}")

        return entries

    # ─── 3. Weather-Sensor Correlation ───────────────────────────────

    async def collect_weather_correlations(self) -> List[KnowledgeEntry]:
        """
        Analyze weather ↔ internal sensor correlations.
        Uses the /info endpoint weather data + trend data to find patterns.
        """
        entries: List[KnowledgeEntry] = []
        try:
            client = await self._get_client()

            # Get current weather from our own /info
            info_resp = await client.get("http://localhost:8082/info")
            if info_resp.status_code != 200:
                return entries

            info = info_resp.json()
            weather_stats = info.get("ai_pipeline", {}).get("weather", {}).get("stats", {})

            if not weather_stats.get("enabled"):
                return entries

            cache = weather_stats.get("last_cached")
            if not cache:
                return entries

            # Try to get trend data for correlation analysis
            sensor_types = ["temperature", "humidity", "co2"]
            farm_ids = ["farm-001"]  # Default demo farm

            for farm_id in farm_ids:
                sensor_summaries = []
                for st in sensor_types:
                    try:
                        trend_resp = await client.get(
                            f"http://localhost:8082/api/trends/{farm_id}/{st}?window=6h"
                        )
                        if trend_resp.status_code == 200:
                            data = trend_resp.json()
                            if data.get("has_data"):
                                sensor_summaries.append({
                                    "type": st,
                                    "mean": data["stats"].get("mean"),
                                    "direction": data["stats"].get("direction"),
                                    "rate": data["stats"].get("rate_of_change"),
                                })
                    except Exception:
                        pass

                if not sensor_summaries:
                    continue

                now = datetime.now(timezone.utc)
                month = now.strftime("%m")
                season_map = {"12": "겨울", "01": "겨울", "02": "겨울",
                              "03": "봄", "04": "봄", "05": "봄",
                              "06": "여름", "07": "여름", "08": "여름",
                              "09": "가을", "10": "가을", "11": "가을"}
                season = season_map.get(month, "?")

                content = (
                    f"## 기상-센서 상관관계 ({season} / {now.strftime('%Y-%m-%d')})\n\n"
                    f"- 농장: {farm_id}\n"
                    f"- 계절: {season}\n\n"
                    f"### 센서 추세 요약 (최근 6시간)\n"
                )
                for s in sensor_summaries:
                    unit = {"temperature": "°C", "humidity": "%", "co2": "ppm"}.get(s["type"], "")
                    content += (
                        f"- **{s['type']}**: 평균 {s['mean']:.1f}{unit}, "
                        f"추세 {s['direction']}, 변화율 {s['rate']:+.2f}/h\n"
                    )

                content += (
                    f"\n### 패턴 분석\n"
                    f"이 데이터는 {season}철 {farm_id} 농장의 센서 추세를 기록합니다. "
                    f"계절별 패턴 분석에 활용하여 선제적 환경 제어에 참고하십시오.\n"
                )

                entry_id = f"weather-corr-{farm_id}-{now.strftime('%Y%m%d-%H')}"
                entries.append(KnowledgeEntry(
                    entry_id=entry_id,
                    source="weather_correlation",
                    category="seasonal",
                    title=f"기상-센서 상관관계 ({farm_id}, {season}, {now.strftime('%m-%d')})",
                    content=content,
                    metadata={
                        "farm_id": farm_id,
                        "season": season,
                        "sensor_summaries": sensor_summaries,
                        "date": now.isoformat(),
                    },
                ))

            self.stats["weather_correlations_collected"] += len(entries)

        except Exception as e:
            logger.warning(f"⚠️ Weather correlation collection failed: {e}")

        return entries

    # ─── 4. Embedding into ChromaDB ──────────────────────────────────

    def _init_embeddings(self):
        """Lazy-init embedding function and ChromaDB"""
        if self._embed_fn is not None:
            return

        try:
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from langchain_community.vectorstores import Chroma

            self._embed_fn = HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )

            chroma_path = Path(CHROMA_DB_PATH)
            chroma_path.mkdir(parents=True, exist_ok=True)

            self._vector_db = Chroma(
                persist_directory=str(chroma_path),
                embedding_function=self._embed_fn,
                collection_name="agri_knowledge",
            )
            logger.info("✅ Knowledge embedding engine initialized")

        except Exception as e:
            logger.warning(f"⚠️ Embedding init failed (RAG disabled): {e}")
            self._embed_fn = None
            self._vector_db = None

    def embed_entries(self, entries: List[KnowledgeEntry]) -> int:
        """Embed knowledge entries into ChromaDB vector store"""
        if not entries:
            return 0

        self._init_embeddings()
        if self._vector_db is None:
            logger.warning("⚠️ Vector DB not available, saving to files only")
            self._save_entries_to_files(entries)
            return 0

        try:
            texts = [e.content for e in entries]
            metadatas = [
                {
                    "entry_id": e.entry_id,
                    "source": e.source,
                    "category": e.category,
                    "title": e.title,
                    "created_at": e.created_at,
                }
                for e in entries
            ]
            ids = [e.entry_id for e in entries]

            self._vector_db.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids,
            )

            for e in entries:
                e.embedded = True

            self.stats["embedded_entries"] += len(entries)
            self.stats["last_embedding"] = datetime.now(timezone.utc).isoformat()
            logger.info(f"✅ Embedded {len(entries)} entries into ChromaDB")

            # Also save to files as backup
            self._save_entries_to_files(entries)

            return len(entries)

        except Exception as e:
            logger.error(f"❌ Embedding failed: {e}", exc_info=True)
            self._save_entries_to_files(entries)
            return 0

    def _save_entries_to_files(self, entries: List[KnowledgeEntry]):
        """Save knowledge entries as markdown files (backup / human-readable)"""
        for entry in entries:
            fname = f"{entry.entry_id}.md"
            fpath = self.generated_path / fname
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(f"# {entry.title}\n\n")
                    f.write(f"- **Source:** {entry.source}\n")
                    f.write(f"- **Category:** {entry.category}\n")
                    f.write(f"- **Created:** {entry.created_at}\n")
                    f.write(f"- **Embedded:** {entry.embedded}\n\n")
                    f.write("---\n\n")
                    f.write(entry.content)
            except Exception as e:
                logger.warning(f"⚠️ Failed to save entry file {fname}: {e}")

    # ─── 5. Manual Knowledge Ingestion ───────────────────────────────

    def add_manual_entry(self, title: str, content: str, category: str = "manual") -> KnowledgeEntry:
        """Add a manual knowledge entry (from API or admin)"""
        now = datetime.now(timezone.utc)
        entry_id = f"manual-{now.strftime('%Y%m%d%H%M%S')}"
        entry = KnowledgeEntry(
            entry_id=entry_id,
            source="manual",
            category=category,
            title=title,
            content=content,
        )
        self.entries.append(entry)
        self.stats["total_entries"] += 1

        # Immediately embed
        count = self.embed_entries([entry])
        logger.info(f"📝 Manual entry added: {title} (embedded={count > 0})")
        return entry

    # ─── 6. Orchestrator: Collect All ────────────────────────────────

    async def collect_all(self) -> Dict[str, Any]:
        """
        Run full knowledge collection cycle:
        1. Extract insight patterns from accumulator
        2. Fetch action outcomes from terra-ops
        3. Analyze weather-sensor correlations
        4. Embed all new entries into ChromaDB
        """
        logger.info("🔄 Starting knowledge collection cycle...")
        new_entries: List[KnowledgeEntry] = []

        # 1. Insight patterns
        try:
            patterns = self.extract_insight_patterns()
            new_entries.extend(patterns)
            logger.info(f"   📊 {len(patterns)} insight patterns extracted")
        except Exception as e:
            logger.warning(f"   ⚠️ Insight pattern extraction failed: {e}")

        # 2. Action outcomes
        try:
            outcomes = await self.collect_action_outcomes()
            new_entries.extend(outcomes)
            logger.info(f"   📋 {len(outcomes)} action outcomes collected")
        except Exception as e:
            logger.warning(f"   ⚠️ Action outcome collection failed: {e}")

        # 3. Weather correlations
        try:
            correlations = await self.collect_weather_correlations()
            new_entries.extend(correlations)
            logger.info(f"   🌤️ {len(correlations)} weather correlations collected")
        except Exception as e:
            logger.warning(f"   ⚠️ Weather correlation collection failed: {e}")

        # 4. Embed all new entries
        embedded = 0
        if new_entries:
            embedded = self.embed_entries(new_entries)
            self.entries.extend(new_entries)
            self.stats["total_entries"] += len(new_entries)

        # 5. Reset accumulator after successful extraction
        if new_entries:
            self.accumulator = InsightAccumulator()

        self.stats["last_collection"] = datetime.now(timezone.utc).isoformat()

        result = {
            "collected": len(new_entries),
            "embedded": embedded,
            "insight_patterns": len([e for e in new_entries if e.source == "insight_pattern"]),
            "action_outcomes": len([e for e in new_entries if e.source == "action_outcome"]),
            "weather_correlations": len([e for e in new_entries if e.source == "weather_correlation"]),
            "timestamp": self.stats["last_collection"],
        }

        logger.info(f"✅ Knowledge collection complete: {result}")
        return result

    # ─── 7. Auto-Collection Loop ─────────────────────────────────────

    async def start_auto_collection(self):
        """Start periodic auto-collection background task"""
        self._collection_task = asyncio.create_task(self._auto_collection_loop())
        self.stats["auto_collect_running"] = True
        logger.info(f"🔄 Auto-collection started (interval: {COLLECTION_INTERVAL_MIN} min)")

    async def _auto_collection_loop(self):
        """Periodic collection loop"""
        try:
            # Initial delay to let services stabilize
            await asyncio.sleep(120)

            while True:
                try:
                    await self.collect_all()
                except Exception as e:
                    logger.error(f"❌ Auto-collection cycle failed: {e}", exc_info=True)

                await asyncio.sleep(COLLECTION_INTERVAL_MIN * 60)

        except asyncio.CancelledError:
            logger.info("🛑 Auto-collection loop cancelled")
            self.stats["auto_collect_running"] = False

    # ─── 8. Stats & Info ─────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge collector statistics"""
        # Count generated files
        gen_files = list(self.generated_path.glob("*.md")) if self.generated_path.exists() else []

        db_count = 0
        if self._vector_db:
            try:
                db_count = self._vector_db._collection.count()
            except Exception:
                pass

        return {
            **self.stats,
            "accumulator_anomalies": sum(self.accumulator.anomaly_counts.values()),
            "accumulator_processed": self.accumulator.total_processed,
            "generated_files": len(gen_files),
            "chroma_document_count": db_count,
            "collection_interval_min": COLLECTION_INTERVAL_MIN,
        }

    def get_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent knowledge entries"""
        recent = sorted(self.entries, key=lambda e: e.created_at, reverse=True)[:limit]
        return [
            {
                "entry_id": e.entry_id,
                "source": e.source,
                "category": e.category,
                "title": e.title,
                "embedded": e.embedded,
                "created_at": e.created_at,
                "content_preview": e.content[:200] + "..." if len(e.content) > 200 else e.content,
            }
            for e in recent
        ]


# ─── Global Singleton ───────────────────────────────────────────────
_collector_instance: Optional[KnowledgeCollector] = None


def get_knowledge_collector() -> KnowledgeCollector:
    """Get or create global KnowledgeCollector instance"""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = KnowledgeCollector()
    return _collector_instance
