"""
Terra-Cortex AI Analysis Microservice
Hybrid AI Architecture: Local Edge AI + Cloud LLM + CloudEvents v1.0
- Local Analyzer: Fast rule-based detection (always runs)
- Cloud Advisor: Detailed LLM recommendations (only for ANOMALY)
- CloudEvents: Standards-compliant event format with trace_id propagation
- Action Plans: AI-generated recommendations with safety conditions
"""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import FastAPI, Header
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from src.local_analyzer import LocalAnalyzer
from src.cloud_advisor import CloudAdvisor
from src.models import SensorData, Insight
from src.weather_provider import get_weather_provider, WeatherProvider
from src.crop_profile import get_crop_profile_provider, CropProfileProvider
from src.timeseries import get_timeseries_analyzer, TimeSeriesAnalyzer
from src.knowledge_collector import get_knowledge_collector, KnowledgeCollector
from src.cloudevents_models import (
    generate_trace_id,
    create_insight_event,
    create_action_plan_event,
    InsightDetectedEvent,
    ActionPlanGeneratedEvent,
    InsightStatus,
    Severity,
    ActionCategory,
    ActionType,
    Priority
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
import os
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC", "raw-sensor-data")
OUTPUT_TOPIC = os.getenv("KAFKA_OUTPUT_TOPIC", "processed-insights")
ACTION_PLAN_TOPIC = os.getenv("KAFKA_ACTION_PLAN_TOPIC", "action-plans")
CONSUMER_GROUP = "terra-cortex-group"

# Global Kafka clients
consumer: AIOKafkaConsumer = None
producer: AIOKafkaProducer = None
kafka_task = None

# Global AI components (Hybrid Architecture)
local_analyzer: LocalAnalyzer = None
cloud_advisor: CloudAdvisor = None
weather_provider: WeatherProvider = None
crop_provider: CropProfileProvider = None
trend_analyzer: TimeSeriesAnalyzer = None
knowledge_collector: KnowledgeCollector = None

# Action Plan Configuration (Safety-First Design)
ACTION_PLAN_CONFIG = {
    "temperature": {
        "high": {"asset": "fan-01", "category": ActionCategory.VENTILATION, "action": ActionType.TURN_ON, "params": {"duration_minutes": 30, "speed_level": "high"}},
        "critical": {"asset": "fan-01", "category": ActionCategory.VENTILATION, "action": ActionType.TURN_ON, "params": {"duration_minutes": 60, "speed_level": "max"}}
    },
    "humidity": {
        "high": {"asset": "dehumidifier-01", "category": ActionCategory.VENTILATION, "action": ActionType.TURN_ON, "params": {"duration_minutes": 20}},
        "low": {"asset": "humidifier-01", "category": ActionCategory.IRRIGATION, "action": ActionType.TURN_ON, "params": {"duration_minutes": 15}}
    },
    "co2": {
        "high": {"asset": "vent-01", "category": ActionCategory.VENTILATION, "action": ActionType.TURN_ON, "params": {"duration_minutes": 45}}
    }
}


async def start_kafka():
    """Initialize and start Kafka consumer and producer with retry logic"""
    global consumer, producer, kafka_task
    
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔄 Kafka connection attempt {attempt}/{max_retries}...")
            
            # Create consumer
            consumer = AIOKafkaConsumer(
                INPUT_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=CONSUMER_GROUP,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            
            # Create producer
            producer = AIOKafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            # Start both
            await consumer.start()
            await producer.start()
            
            logger.info(f"✅ Kafka started: consuming from '{INPUT_TOPIC}', producing to '{OUTPUT_TOPIC}'")
            
            # Start consuming in background
            kafka_task = asyncio.create_task(consume_messages())
            return
            
        except Exception as e:
            logger.warning(f"⚠️ Kafka connection attempt {attempt} failed: {e}")
            if attempt < max_retries:
                logger.info(f"⏳ Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ Failed to start Kafka after {max_retries} attempts")
                raise


async def stop_kafka():
    """Stop Kafka consumer and producer"""
    global consumer, producer, kafka_task
    
    if kafka_task:
        kafka_task.cancel()
        try:
            await kafka_task
        except asyncio.CancelledError:
            pass
    
    if consumer:
        await consumer.stop()
    if producer:
        await producer.stop()
    
    logger.info("🛑 Kafka stopped")


async def consume_messages():
    """
    Async loop to consume messages from Kafka.
    Implements Hybrid AI Architecture with CloudEvents v1.0:
    1. Generate trace_id for distributed tracing
    2. Local Analyzer runs first (fast, always)
    3. Cloud Advisor runs only for ANOMALY (detailed, conditional)
    4. Generate Action Plans for anomalies (requires human approval)
    """
    logger.info("🔄 Starting Kafka consumer loop with Hybrid AI + CloudEvents v1.0...")
    logger.info("   - Local Analyzer: Always active (Edge AI)")
    logger.info(f"   - Cloud Advisor: {cloud_advisor.enabled and 'Enabled (triggers on ANOMALY)' or 'Disabled (no API key)'}")
    logger.info(f"   - Weather Provider: {weather_provider.enabled and 'Enabled' or 'Disabled (no WEATHER_API_KEY)'}")
    logger.info(f"   - Crop Profile: Enabled (terra-ops 연동)")
    logger.info(f"   - Trend Analyzer: Enabled (InfluxDB 시계열)")
    logger.info("   - CloudEvents: Enabled with trace_id propagation")
    logger.info("   - Action Plans: Auto-generated for ANOMALY (requires approval)")
    
    try:
        async for message in consumer:
            try:
                # Generate trace_id for this event chain (distributed tracing)
                trace_id = generate_trace_id()
                
                # Parse sensor data
                sensor_data_dict = message.value
                sensor_data = SensorData(**sensor_data_dict)
                
                logger.info(f"📥 [{trace_id[:20]}...] Received: {sensor_data.farmId} - {sensor_data.sensorType}: {sensor_data.value}")
                
                # STEP 0: Fetch weather context (cached, non-blocking)
                weather = await weather_provider.get_weather() if weather_provider.enabled else None
                if weather:
                    local_analyzer.set_weather_context(weather)
                    logger.info(f"   🌤️ Weather context: {weather.temperature}°C, {weather.humidity}%, {weather.description}")
                
                # STEP 0.5: Fetch crop profile context (cached, terra-ops 연동)
                crop_ctx = await crop_provider.get_crop_context(sensor_data.farmId)
                if crop_ctx and crop_ctx.has_crop_profile:
                    local_analyzer.set_crop_context(crop_ctx)
                    primary = crop_ctx.get_primary_condition()
                    if primary:
                        logger.info(f"   🌱 Crop context: {primary.crop_name} - {primary.current_stage} ({primary.days_since_planting}일차)")
                else:
                    local_analyzer.set_crop_context(None)
                
                # STEP 0.75: Fetch time-series trend context (cached, InfluxDB)
                trend_ctx = None
                try:
                    trend_ctx = await trend_analyzer.get_trend_context(
                        sensor_data.farmId, sensor_data.sensorType.lower()
                    )
                    if trend_ctx and trend_ctx.has_data:
                        local_analyzer.set_trend_context(trend_ctx)
                        logger.info(
                            f"   📈 Trend: {trend_ctx.stats.direction}"
                            f" (MA:{trend_ctx.stats.moving_avg:.1f},"
                            f" rate:{trend_ctx.stats.rate_of_change:+.2f}/h,"
                            f" spike:{trend_ctx.stats.is_spike})"
                        )
                    else:
                        local_analyzer.set_trend_context(None)
                except Exception as te:
                    logger.warning(f"   ⚠️ Trend context fetch failed: {te}")
                    local_analyzer.set_trend_context(None)
                
                # STEP 1: Local Edge AI Analysis (always runs, fast)
                insight = local_analyzer.analyze(sensor_data)
                logger.info(f"   🔍 Local Analyzer: {insight.status} ({insight.severity})")
                
                # STEP 2: Cloud LLM Advisory (only for ANOMALY, smart trigger)
                if insight.status == "ANOMALY" and cloud_advisor.enabled:
                    logger.info(f"   🤖 Triggering Cloud Advisor for ANOMALY...")
                    llm_recommendation = await cloud_advisor.get_recommendation(sensor_data, insight, weather, crop_ctx, trend_ctx)
                    
                    if llm_recommendation:
                        insight.llmRecommendation = llm_recommendation
                        logger.info(f"   ✅ Cloud LLM recommendation added ({len(llm_recommendation)} chars)")
                    else:
                        logger.warning("   ⚠️ Cloud LLM recommendation failed, using local analysis only")
                
                # STEP 3: Send CloudEvents-compliant Insight Event
                await send_insight_event(trace_id, sensor_data, insight)
                
                # STEP 4: Generate Action Plan for ANOMALY (requires human approval)
                if insight.status == "ANOMALY":
                    await generate_action_plan(trace_id, sensor_data, insight)
                
                # STEP 5: Accumulate insight for knowledge collection
                if knowledge_collector:
                    knowledge_collector.accumulate_insight(insight.model_dump(mode='json'))
                
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}", exc_info=True)
    
    except asyncio.CancelledError:
        logger.info("🛑 Consumer loop cancelled")
    except Exception as e:
        logger.error(f"❌ Consumer loop error: {e}", exc_info=True)


async def send_insight_event(trace_id: str, sensor_data: SensorData, insight: Insight):
    """Send CloudEvents-compliant insight event to Kafka"""
    try:
        # Map severity string to enum
        severity_map = {"info": Severity.INFO, "warning": Severity.WARNING, "critical": Severity.CRITICAL}
        severity = severity_map.get(insight.severity, Severity.INFO)
        
        # Create CloudEvents-compliant insight event
        insight_event = create_insight_event(
            trace_id=trace_id,
            farm_id=insight.farmId,
            sensor_type=insight.sensorType,
            status=InsightStatus.ANOMALY if insight.status == "ANOMALY" else InsightStatus.NORMAL,
            severity=severity,
            message=insight.message,
            raw_value=insight.rawValue,
            confidence=insight.confidence,
            llm_recommendation=insight.llmRecommendation
        )
        
        # Send to Kafka with trace_id in headers
        await producer.send_and_wait(
            OUTPUT_TOPIC,
            value=insight_event.model_dump(mode='json'),
            key=insight.farmId.encode('utf-8'),
            headers=[("trace_id", trace_id.encode('utf-8'))]
        )
        
        logger.info(f"📤 [{trace_id[:20]}...] Sent CloudEvent: {insight.farmId} - {insight.status} ({insight.severity})")
        
    except Exception as e:
        logger.error(f"❌ Failed to send insight event: {e}")


async def generate_action_plan(trace_id: str, sensor_data: SensorData, insight: Insight):
    """Generate action plan for anomaly (Safety-First: requires human approval)"""
    try:
        sensor_type = sensor_data.sensorType.lower()
        severity = insight.severity.lower()
        
        # Check if we have an action plan config for this sensor type
        if sensor_type not in ACTION_PLAN_CONFIG:
            logger.info(f"   ℹ️ No action plan configured for sensor type: {sensor_type}")
            return
        
        # Get severity-based action config (fall back to 'high' if specific severity not found)
        severity_key = severity if severity in ACTION_PLAN_CONFIG[sensor_type] else "high"
        if severity_key not in ACTION_PLAN_CONFIG[sensor_type]:
            logger.info(f"   ℹ️ No action plan for {sensor_type} at severity: {severity}")
            return
            
        config = ACTION_PLAN_CONFIG[sensor_type][severity_key]
        
        # Map severity to priority
        priority_map = {"warning": Priority.MEDIUM, "critical": Priority.HIGH}
        priority = priority_map.get(severity, Priority.MEDIUM)
        
        # Create CloudEvents-compliant action plan
        action_plan_event = create_action_plan_event(
            trace_id=trace_id,
            farm_id=sensor_data.farmId,
            target_asset_id=config["asset"],
            action_category=config["category"],
            action_type=config["action"],
            reasoning=f"{insight.message}. {insight.llmRecommendation or 'Automatic recommendation based on threshold analysis.'}",
            priority=priority,
            parameters=config.get("params", {}),
            safety_conditions=[
                f"{config['asset']}_device_online",
                "no_maintenance_mode",
                f"{sensor_type}_above_threshold"
            ],
            expires_minutes=30
        )
        
        # Send to action-plans topic (terra-ops will consume and validate)
        await producer.send_and_wait(
            ACTION_PLAN_TOPIC,
            value=action_plan_event.model_dump(mode='json'),
            key=sensor_data.farmId.encode('utf-8'),
            headers=[("trace_id", trace_id.encode('utf-8'))]
        )
        
        logger.info(f"📤 [{trace_id[:20]}...] Action Plan generated: {config['asset']} -> {config['action'].value}")
        logger.info(f"   ⏳ Awaiting human approval in terra-ops...")
        
    except Exception as e:
        logger.error(f"❌ Failed to generate action plan: {e}", exc_info=True)


async def send_insight(insight: Insight):
    """Send insight to Kafka output topic (legacy format for backward compatibility)"""
    try:
        insight_dict = insight.model_dump(mode='json')
        
        await producer.send_and_wait(
            OUTPUT_TOPIC,
            value=insight_dict,
            key=insight.farmId.encode('utf-8')
        )
        
        logger.info(f"📤 Sent: {insight.farmId} - {insight.status} ({insight.severity})")
        
    except Exception as e:
        logger.error(f"❌ Failed to send insight: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global local_analyzer, cloud_advisor, weather_provider, crop_provider, trend_analyzer, knowledge_collector
    
    logger.info("🧠 Terra-Cortex Hybrid AI Engine starting...")
    
    # Initialize AI components
    local_analyzer = LocalAnalyzer()
    cloud_advisor = CloudAdvisor()
    weather_provider = get_weather_provider()
    crop_provider = get_crop_profile_provider()
    trend_analyzer = get_timeseries_analyzer()
    knowledge_collector = get_knowledge_collector()
    
    logger.info("   ✅ Local Analyzer initialized (Edge AI)")
    logger.info(f"   {'✅' if cloud_advisor.enabled else '⚠️'} Cloud Advisor {'enabled' if cloud_advisor.enabled else 'disabled (set OPENAI_API_KEY to enable)'}")
    logger.info(f"   {'✅' if weather_provider.enabled else '⚠️'} Weather Provider {'enabled' if weather_provider.enabled else 'disabled (set WEATHER_API_KEY to enable)'}")
    logger.info(f"   ✅ Crop Profile Provider initialized (terra-ops 연동)")
    logger.info(f"   ✅ Trend Analyzer initialized (InfluxDB 시계열 분석)")
    logger.info(f"   ✅ Knowledge Collector initialized (지식 축적 파이프라인)")
    
    # Start Kafka
    await start_kafka()
    
    # Start auto knowledge collection
    await knowledge_collector.start_auto_collection()
    
    yield
    
    logger.info("🛑 Terra-Cortex Hybrid AI Engine shutting down...")
    await knowledge_collector.close()
    await stop_kafka()


# FastAPI application
app = FastAPI(
    title="Terra-Cortex Hybrid AI Engine",
    version="2.0.0",
    description="🧠 Hybrid AI: Local Edge Analyzer + Cloud LLM Advisor",
    lifespan=lifespan
)


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint"""
    return {
        "service": "terra-cortex",
        "version": "2.0.0",
        "architecture": "hybrid-ai",
        "status": "running",
        "description": "Hybrid AI Analysis Engine: Local Edge AI + Cloud LLM",
        "local_analyzer": local_analyzer.get_stats() if local_analyzer else {},
        "cloud_advisor": cloud_advisor.get_stats() if cloud_advisor else {},
        "weather_provider": weather_provider.get_stats() if weather_provider else {},
        "knowledge_collector": knowledge_collector.get_stats() if knowledge_collector else {}
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "healthy",
        "kafka_consumer_running": consumer is not None and not consumer._closed,
        "kafka_producer_running": producer is not None and not producer._closed,
        "input_topic": INPUT_TOPIC,
        "output_topic": OUTPUT_TOPIC
    }


@app.get("/info")
async def info() -> Dict[str, Any]:
    """Service information with hybrid AI details"""
    return {
        "service": "terra-cortex",
        "architecture": "hybrid-ai",
        "description": "Hybrid AI-powered sensor anomaly detection",
        "kafka": {
            "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
            "input_topic": INPUT_TOPIC,
            "output_topic": OUTPUT_TOPIC,
            "consumer_group": CONSUMER_GROUP
        },
        "ai_pipeline": {
            "stage_1": {
                "name": "Local Edge Analyzer",
                "type": "rule-based",
                "speed": "instant (<1ms)",
                "cost": "free",
                "always_runs": True,
                "stats": local_analyzer.get_stats() if local_analyzer else {}
            },
            "stage_2": {
                "name": "Cloud LLM Advisor",
                "type": "llm-powered",
                "model": cloud_advisor.model if cloud_advisor and cloud_advisor.enabled else None,
                "trigger": "ANOMALY only",
                "enabled": cloud_advisor.enabled if cloud_advisor else False,
                "stats": cloud_advisor.get_stats() if cloud_advisor else {}
            },
            "weather": {
                "name": "Weather Context Provider",
                "type": "external-api",
                "enabled": weather_provider.enabled if weather_provider else False,
                "stats": weather_provider.get_stats() if weather_provider else {}
            },
            "crop_profile": {
                "name": "Crop Profile Provider",
                "type": "terra-ops-api",
                "enabled": crop_provider.enabled if crop_provider else False,
                "stats": crop_provider.get_stats() if crop_provider else {}
            },
            "trend_analyzer": {
                "name": "Time Series Trend Analyzer",
                "type": "influxdb-flux",
                "enabled": trend_analyzer is not None,
                "config": trend_analyzer.get_config() if trend_analyzer else {}
            },
            "knowledge_collector": {
                "name": "Knowledge Accumulation Pipeline",
                "type": "auto-rag-enrichment",
                "enabled": knowledge_collector is not None,
                "stats": knowledge_collector.get_stats() if knowledge_collector else {}
            }
        }
    }


# ─── Time Series Trend REST API ─────────────────────────────────────
@app.get("/api/trends/{farm_id}/{sensor_type}")
async def get_trend(farm_id: str, sensor_type: str, window: str = "1h"):
    """Get time-series trend analysis for a farm sensor"""
    if not trend_analyzer:
        return {"error": "Trend analyzer not initialized"}
    ctx = await trend_analyzer.get_trend_context(farm_id, sensor_type, window)
    if not ctx or not ctx.has_data:
        return {"farm_id": farm_id, "sensor_type": sensor_type, "has_data": False, "message": "No data available"}
    return {
        "farm_id": ctx.farm_id,
        "sensor_type": ctx.sensor_type,
        "has_data": True,
        "stats": {
            "mean": ctx.stats.mean,
            "std": ctx.stats.std,
            "min": ctx.stats.min_val,
            "max": ctx.stats.max_val,
            "count": ctx.stats.count,
            "latest": ctx.stats.latest,
            "direction": ctx.stats.direction,
            "rate_of_change": ctx.stats.rate_of_change,
            "moving_avg": ctx.stats.moving_avg,
            "deviation_from_ma": ctx.stats.deviation_from_ma,
            "is_spike": ctx.stats.is_spike,
            "predicted_next": ctx.stats.predicted_next,
            "period": ctx.stats.period,
        },
        "recent_points": [{"time": p.time, "value": p.value} for p in (ctx.recent_points or [])[-30:],],
        "message": ctx.message,
    }


@app.get("/api/trends/{farm_id}/{sensor_type}/daily")
async def get_daily_trend(farm_id: str, sensor_type: str, days: int = 7):
    """Get daily aggregated stats for a farm sensor"""
    if not trend_analyzer:
        return {"error": "Trend analyzer not initialized"}
    rows = await trend_analyzer.query_daily_stats(farm_id, sensor_type, days)
    return {
        "farm_id": farm_id,
        "sensor_type": sensor_type,
        "days": days,
        "data": [{"time": r.time, "value": r.value} for r in rows],
    }


@app.get("/api/trends/{farm_id}/{sensor_type}/hourly")
async def get_hourly_pattern(farm_id: str, sensor_type: str, days: int = 7):
    """Get hourly pattern (average by hour of day)"""
    if not trend_analyzer:
        return {"error": "Trend analyzer not initialized"}
    patterns = await trend_analyzer.query_hourly_pattern(farm_id, sensor_type, days)
    return {
        "farm_id": farm_id,
        "sensor_type": sensor_type,
        "days": days,
        "pattern": [
            {"hour": p.hour, "avg": p.avg_value, "min": p.min_value, "max": p.max_value}
            for p in patterns
        ],
    }


# ─── Knowledge Accumulation REST API ────────────────────────────────
@app.get("/api/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge collector statistics"""
    if not knowledge_collector:
        return {"error": "Knowledge collector not initialized"}
    return knowledge_collector.get_stats()


@app.get("/api/knowledge/entries")
async def get_knowledge_entries(limit: int = 50):
    """Get recent knowledge entries"""
    if not knowledge_collector:
        return {"error": "Knowledge collector not initialized"}
    return {
        "entries": knowledge_collector.get_entries(limit),
        "total": knowledge_collector.stats["total_entries"],
    }


@app.post("/api/knowledge/collect")
async def trigger_collection():
    """Trigger manual knowledge collection cycle"""
    if not knowledge_collector:
        return {"error": "Knowledge collector not initialized"}
    result = await knowledge_collector.collect_all()
    return result


@app.post("/api/knowledge/ingest")
async def ingest_manual_knowledge(title: str, content: str, category: str = "manual"):
    """Manually add a knowledge entry and embed into RAG"""
    if not knowledge_collector:
        return {"error": "Knowledge collector not initialized"}
    entry = knowledge_collector.add_manual_entry(title, content, category)
    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "embedded": entry.embedded,
        "created_at": entry.created_at,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
