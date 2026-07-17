package com.terraneuron.sense.service;

import com.terraneuron.sense.model.SensorData;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

import java.time.Instant;

/**
 * Kafka Producer 서비스
 * 센서 데이터를 Kafka 토픽으로 전송
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaProducerService {

    private final KafkaTemplate<String, SensorData> kafkaTemplate;

    @Value("${kafka.topic.raw-sensor-data}")
    private String rawSensorDataTopic;

    public void sendSensorData(SensorData sensorData) {
        try {
            if (sensorData.getTimestamp() == null) {
                sensorData.setTimestamp(Instant.now());
            }
            String eventId = sensorData.ensureEventId();

            kafkaTemplate.send(
                            MessageBuilder.withPayload(sensorData)
                                    .setHeader("kafka_topic", rawSensorDataTopic)
                                    .setHeader("kafka_messageKey", eventId)
                                    .setHeader("event_id", eventId.getBytes(java.nio.charset.StandardCharsets.UTF_8))
                                    .build()
                    )
                    .whenComplete((result, ex) -> {
                        if (ex == null) {
                            log.info(
                                    "✅ Kafka 전송 성공: eventId={}, sensorId={}, type={}, value={}",
                                    eventId,
                                    sensorData.getSensorId(),
                                    sensorData.getSensorType(),
                                    sensorData.getValue()
                            );
                        } else {
                            log.error("❌ Kafka 전송 실패: eventId={}, error={}", eventId, ex.getMessage());
                        }
                    });
        } catch (Exception e) {
            log.error("❌ Kafka 전송 중 에러 발생: {}", e.getMessage(), e);
        }
    }
}
