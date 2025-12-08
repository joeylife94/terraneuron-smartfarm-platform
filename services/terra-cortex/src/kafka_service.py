import json
import logging
from kafka import KafkaConsumer, KafkaProducer
from src.config import settings
from src.models import SensorData, Insight
from src.ai_engine import AnomalyDetector
import threading

logger = logging.getLogger(__name__)


class KafkaService:
    """Kafka Consumer/Producer 통합 서비스"""
    
    def __init__(self):
        self.consumer = None
        self.producer = None
        self.ai_engine = AnomalyDetector(threshold=settings.anomaly_threshold)
        self.running = False
        self.consumer_thread = None
    
    def start(self):
        """Kafka 소비자 시작"""
        try:
            self.consumer = KafkaConsumer(
                settings.kafka_input_topic,
                bootstrap_servers=settings.kafka_bootstrap_servers,
                group_id=settings.kafka_consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )
            
            self.producer = KafkaProducer(
                bootstrap_servers=settings.kafka_bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            
            self.running = True
            self.consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
            self.consumer_thread.start()
            
            logger.info(f"✅ Kafka 서비스 시작: {settings.kafka_input_topic} -> {settings.kafka_output_topic}")
            
        except Exception as e:
            logger.error(f"❌ Kafka 서비스 시작 실패: {e}")
            raise
    
    def stop(self):
        """Kafka 소비자 종료"""
        self.running = False
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()
        logger.info("🛑 Kafka 서비스 종료")
    
    def _consume_loop(self):
        """메시지 소비 루프"""
        logger.info("🔄 Kafka 소비 시작...")
        
        for message in self.consumer:
            if not self.running:
                break
            
            try:
                sensor_data = SensorData(**message.value)
                logger.info(f"📥 수신: {sensor_data.sensor_id} - {sensor_data.sensor_type}: {sensor_data.value}")
                
                # AI 분석 수행
                insight = self.ai_engine.create_insight(sensor_data)
                
                # Kafka로 결과 전송
                self._send_insight(insight)
                
            except Exception as e:
                logger.error(f"❌ 메시지 처리 중 에러: {e}", exc_info=True)
    
    def _send_insight(self, insight: Insight):
        """분석 결과를 Kafka로 전송"""
        try:
            insight_dict = insight.model_dump(by_alias=True, mode='json')
            
            self.producer.send(
                settings.kafka_output_topic,
                value=insight_dict,
                key=insight.sensor_id.encode('utf-8')
            )
            
            logger.info(f"📤 전송: {insight.sensor_id} - {insight.insight_type} ({insight.severity})")
            
        except Exception as e:
            logger.error(f"❌ Kafka 전송 실패: {e}")


# 전역 인스턴스
kafka_service = KafkaService()
