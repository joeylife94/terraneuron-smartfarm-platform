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

    @KafkaListener(
            topics = "terra.control.feedback",
            groupId = "${spring.kafka.consumer.group-id}"
    )
    @Transactional
    public void onFeedback(Map<String, Object> feedbackEvent) {
        try {
            @SuppressWarnings("unchecked")
            Map<String, Object> data = (Map<String, Object>) feedbackEvent.get("data");
            if (data == null) {
                log.warn("⚠️ 잘못된 피드백 이벤트: data 필드 누락");
                return;
            }

            String traceId = (String) data.getOrDefault("trace_id", "");
            String commandId = (String) data.getOrDefault("command_id", "");
            String planId = (String) data.getOrDefault("plan_id", "");
            String status = (String) data.getOrDefault("status", "UNKNOWN");
            String error = (String) data.getOrDefault("error", "");
            String farmId = (String) data.getOrDefault("farm_id", "");
            String assetId = (String) data.getOrDefault("target_asset_id", "");

            log.info("📥 명령 피드백 수신: plan={}, cmd={}, status={}", planId, commandId, status);

            // 해당 액션 플랜 업데이트
            if (planId != null && !planId.isEmpty()) {
                Optional<ActionPlan> optPlan = actionPlanRepository.findByPlanId(planId);
                if (optPlan.isPresent()) {
                    ActionPlan plan = optPlan.get();
                    updatePlanFromFeedback(plan, status, error, commandId);
                } else {
                    log.warn("⚠️ 피드백 대상 플랜 없음: {}", planId);
                }
            }

            // 감사 로그
            auditService.logCommandFeedback(traceId, commandId, planId, farmId, assetId, status, error);

        } catch (Exception e) {
            log.error("❌ 피드백 처리 실패: {}", e.getMessage(), e);
        }
    }

    private void updatePlanFromFeedback(ActionPlan plan, String status, String error, String commandId) {
        switch (status) {
            case "DELIVERED":
                // 명령이 MQTT로 전달됨 — 디바이스 실행 대기
                plan.setExecutionResult("DELIVERED_TO_DEVICE");
                log.info("   📡 명령 전달 확인: {} → MQTT", plan.getPlanId());
                break;

            case "EXECUTED":
                // 디바이스가 실행 완료
                plan.setStatus(ActionPlan.PlanStatus.EXECUTED);
                plan.setExecutedAt(Instant.now());
                plan.setExecutionResult("DEVICE_CONFIRMED");
                log.info("   ✅ 디바이스 실행 확인: {}", plan.getPlanId());
                break;

            case "FAILED":
                // 명령 전달 또는 디바이스 실행 실패
                plan.setStatus(ActionPlan.PlanStatus.FAILED);
                plan.setExecutionError(error);
                log.warn("   ❌ 명령 실행 실패: {} — {}", plan.getPlanId(), error);
                break;

            default:
                plan.setExecutionResult("FEEDBACK:" + status);
                log.info("   ℹ️ 피드백: {} → {}", plan.getPlanId(), status);
        }

        actionPlanRepository.save(plan);
    }
}
