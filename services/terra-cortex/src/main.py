"""
Terra-Cortex AI Analysis Microservice
Main FastAPI application with async Kafka consumer/producer
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from src.logic import analyze_sensor_data
from src.models import SensorData, Insight

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
CONSUMER_GROUP = "terra-cortex-group"

# Global Kafka clients
consumer: AIOKafkaConsumer = None
producer: AIOKafkaProducer = None
kafka_task = None


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
    """Async loop to consume messages from Kafka"""
    logger.info("🔄 Starting Kafka consumer loop...")
    
    try:
        async for message in consumer:
            try:
                # Parse sensor data
                sensor_data_dict = message.value
                sensor_data = SensorData(**sensor_data_dict)
                
                logger.info(f"📥 Received: {sensor_data.farmId} - {sensor_data.sensorType}: {sensor_data.value}")
                
                # Analyze with AI logic
                insight = analyze_sensor_data(sensor_data)
                
                # Send result to output topic
                await send_insight(insight)
                
            except Exception as e:
                logger.error(f"❌ Error processing message: {e}", exc_info=True)
    
    except asyncio.CancelledError:
        logger.info("🛑 Consumer loop cancelled")
    except Exception as e:
        logger.error(f"❌ Consumer loop error: {e}", exc_info=True)


async def send_insight(insight: Insight):
    """Send insight to Kafka output topic"""
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
    logger.info("🧠 Terra-Cortex AI Engine starting...")
    await start_kafka()
    yield
    logger.info("🛑 Terra-Cortex AI Engine shutting down...")
    await stop_kafka()


# FastAPI application
app = FastAPI(
    title="Terra-Cortex AI Engine",
    version="1.0.0",
    description="🧠 AI-powered anomaly detection for smart farm sensor data",
    lifespan=lifespan
)


@app.get("/")
async def root() -> Dict[str, Any]:
    """Root endpoint"""
    return {
        "service": "terra-cortex",
        "version": "1.0.0",
        "status": "running",
        "description": "AI Analysis Engine for TerraNeuron Platform"
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
    """Service information"""
    return {
        "service": "terra-cortex",
        "description": "AI-powered sensor anomaly detection",
        "kafka": {
            "bootstrap_servers": KAFKA_BOOTSTRAP_SERVERS,
            "input_topic": INPUT_TOPIC,
            "output_topic": OUTPUT_TOPIC,
            "consumer_group": CONSUMER_GROUP
        },
        "logic": {
            "temperature_threshold": 30,
            "humidity_threshold": 40,
            "detection_mode": "rule-based (MVP)"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8082)
