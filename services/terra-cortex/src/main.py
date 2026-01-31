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
                
                # STEP 1: Local Edge AI Analysis (always runs, fast)
                insight = local_analyzer.analyze(sensor_data)
                logger.info(f"   🔍 Local Analyzer: {insight.status} ({insight.severity})")
                
                # STEP 2: Cloud LLM Advisory (only for ANOMALY, smart trigger)
                if insight.status == "ANOMALY" and cloud_advisor.enabled:
                    logger.info(f"   🤖 Triggering Cloud Advisor for ANOMALY...")
                    llm_recommendation = await cloud_advisor.get_recommendation(sensor_data, insight)
                    
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
    global local_analyzer, cloud_advisor
    
    logger.info("🧠 Terra-Cortex Hybrid AI Engine starting...")
    
    # Initialize AI components
    local_analyzer = LocalAnalyzer()
    cloud_advisor = CloudAdvisor()
    
    logger.info("   ✅ Local Analyzer initialized (Edge AI)")
    logger.info(f"   {'✅' if cloud_advisor.enabled else '⚠️'} Cloud Advisor {'enabled' if cloud_advisor.enabled else 'disabled (set OPENAI_API_KEY to enable)'}")
    
    # Start Kafka
    await start_kafka()
    
    yield
    
    logger.info("🛑 Terra-Cortex Hybrid AI Engine shutting down...")
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
        "cloud_advisor": cloud_advisor.get_stats() if cloud_advisor else {}
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
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
