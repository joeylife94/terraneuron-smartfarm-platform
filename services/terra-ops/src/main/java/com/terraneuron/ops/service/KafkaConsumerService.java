package com.terraneuron.ops.service;

import com.terraneuron.ops.dto.InsightDto;
import com.terraneuron.ops.entity.Insight;
import com.terraneuron.ops.repository.InsightRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

/**
 * Kafka Consumer Service
 * Consumes processed insights from terra-cortex AI analysis
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaConsumerService {

    private final InsightRepository insightRepository;

    @KafkaListener(topics = "processed-insights", groupId = "${spring.kafka.consumer.group-id}")
    public void consumeInsight(InsightDto insightDto) {
        try {
            log.info("📥 Kafka Received: farmId={}, status={}, message={}", 
                    insightDto.getFarmId(), 
                    insightDto.getStatus(), 
                    insightDto.getMessage());

            // DTO -> Entity mapping and save
            Insight insight = Insight.builder()
                    .farmId(insightDto.getFarmId())
                    .status(insightDto.getStatus())
                    .message(insightDto.getMessage())
                    .timestamp(insightDto.getTimestamp())
                    .build();

            insightRepository.save(insight);
            log.info("✅ Insight saved: ID={}", insight.getId());

        } catch (Exception e) {
            log.error("❌ Kafka message processing failed: {}", e.getMessage(), e);
        }
    }
}
