package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.repository.ActionPlanRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

/**
 * 제어 명령 피드백 소비자
 *
 * 루프 완성:
 *   AI 분석 → 액션플랜 → 승인 → 명령 전송 → MQTT 디바이스 → 피드백 → 이 Consumer → DB 갱신
 *
 * Kafka 토픽: terra.control.feedback
 * 발신: terra-sense (DeviceCommandConsumer)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CommandFeedbackConsumer {

    private final ActionPlanRepository actionPlanRepository;
    private final AuditService auditService;
    private final ContractSchemaValidator contractSchemaValidator;

    @KafkaListener(
            topics = "terra.control.feedback",
            groupId = "${spring.kafka.consumer.group-id}"
    )
    @Transactional
    public void onFeedback(Map<String, Object> feedbackEvent) {
        try {
            contractSchemaValidator.validate(
                    ContractSchemaValidator.FEEDBACK_SCHEMA, feedbackEvent);

            @SuppressWarnings("unchecked")
            Map<String, Object> data = (Map<String, Object>) feedbackEvent.get("data");
            if (data == null) {
                throw new IllegalArgumentException("Invalid command feedback event: missing data field");
            }

            String traceId = (String) data.getOrDefault("trace_id", "");
            String commandId = (String) data.getOrDefault("command_id", "");
            String planId = (String) data.getOrDefault("plan_id", "");
            String status = (String) data.getOrDefault("status", "UNKNOWN");
            String error = (String) data.getOrDefault("error", "");
            String farmId = (String) data.getOrDefault("farm_id", "");
            String assetId = (String) data.getOrDefault("target_asset_id", "");

            log.info("📥 명령 피드백 수신: plan={}, cmd={}, status={}", planId, commandId, status);

            if (planId != null && !planId.isEmpty()) {
                Optional<ActionPlan> optPlan = actionPlanRepository.findByPlanId(planId);
                if (optPlan.isPresent()) {
                    ActionPlan plan = optPlan.get();
                    updatePlanFromFeedback(plan, status, error, commandId);
                } else {
                    log.warn("⚠️ 피드백 대상 플랜 없음: {}", planId);
                }
            }

            // Only terminal device outcomes are recorded as execution audit events.
            if ("EXECUTED".equals(status) || "FAILED".equals(status)) {
                auditService.logCommandFeedback(
                        traceId, commandId, planId, farmId, assetId, status, error);
            }

        } catch (Exception e) {
            log.error("❌ 피드백 처리 실패: {}", e.getMessage(), e);
            throw new IllegalStateException("Failed to process command feedback event", e);
        }
    }

    private void updatePlanFromFeedback(ActionPlan plan, String status, String error, String commandId) {
        switch (status) {
            case "DELIVERED":
                // MQTT publish success proves delivery to the broker, not device execution.
                plan.setStatus(ActionPlan.PlanStatus.DELIVERED);
                plan.setExecutionResult("MQTT_PUBLISH_CONFIRMED:" + commandId);
                plan.setExecutionError(null);
                log.info("   📡 MQTT 전달 확인: plan={} cmd={}", plan.getPlanId(), commandId);
                break;

            case "EXECUTED":
                // This feedback must originate from an actual device-confirmed completion path.
                plan.setStatus(ActionPlan.PlanStatus.EXECUTED);
                plan.setExecutedAt(Instant.now());
                plan.setExecutionResult("DEVICE_CONFIRMED:" + commandId);
                plan.setExecutionError(null);
                log.info("   ✅ 디바이스 실행 확인: plan={} cmd={}", plan.getPlanId(), commandId);
                break;

            case "FAILED":
                // The current terra-sense bridge emits FAILED only when MQTT publication fails.
                plan.setStatus(ActionPlan.PlanStatus.DELIVERY_FAILED);
                plan.setExecutionResult("MQTT_DELIVERY_FAILED:" + commandId);
                plan.setExecutionError(error);
                log.warn("   ❌ 명령 전달 실패: plan={} cmd={} error={}",
                        plan.getPlanId(), commandId, error);
                break;

            default:
                plan.setExecutionResult("FEEDBACK:" + status + ":" + commandId);
                log.info("   ℹ️ 피드백: {} → {}", plan.getPlanId(), status);
        }

        actionPlanRepository.save(plan);
    }
}
