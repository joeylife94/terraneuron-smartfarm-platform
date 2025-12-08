package com.terraneuron.ops.service;

import com.terraneuron.ops.dto.InsightDto;
import com.terraneuron.ops.entity.Insight;
import com.terraneuron.ops.repository.InsightRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

/**
 * Kafka Consumer 서비스
 * AI 분석 결과를 수신하여 데이터베이스에 저장
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class KafkaConsumerService {

    private final InsightRepository insightRepository;

    @KafkaListener(topics = "${kafka.topic.processed-insights}", groupId = "${spring.kafka.consumer.group-id}")
    public void consumeInsight(InsightDto insightDto) {
        try {
            log.info("📥 Kafka 수신: sensorId={}, type={}, severity={}", 
                    insightDto.getSensorId(), 
                    insightDto.getInsightType(), 
                    insightDto.getSeverity());

            // DTO -> Entity 변환 및 저장
            Insight insight = Insight.builder()
                    .sensorId(Long.parseLong(insightDto.getSensorId().replaceAll("[^0-9]", "")))
                    .insightType(insightDto.getInsightType())
                    .severity(insightDto.getSeverity())
                    .message(insightDto.getMessage())
                    .confidenceScore(insightDto.getConfidenceScore())
                    .detectedAt(insightDto.getDetectedAt())
                    .build();

            insightRepository.save(insight);
            log.info("✅ 인사이트 저장 완료: ID={}", insight.getInsightId());

        } catch (Exception e) {
            log.error("❌ Kafka 메시지 처리 실패: {}", e.getMessage(), e);
        }
    }
}
