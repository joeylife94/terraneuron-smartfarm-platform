package com.terraneuron.ops.repository;

import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.AuditLog;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.TestPropertySource;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@TestPropertySource(properties = {
        "spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.H2Dialect",
        "spring.flyway.enabled=false",
        "spring.jpa.hibernate.ddl-auto=create-drop"
})
class AuditLogRepositoryTest {

    @Autowired
    private AuditLogRepository auditLogRepository;

    @Autowired
    private ActionPlanRepository actionPlanRepository;

    @Test
    void planHistoryIncludesCorrelatedCommandEventsInTimestampOrderWithoutMixingOtherCommands() {
        String planId = "plan-audit-1";
        String commandId = "cmd-audit-1";
        String traceId = "trace-audit-1";
        Instant base = Instant.parse("2026-09-01T00:00:00Z");

        actionPlanRepository.saveAndFlush(ActionPlan.builder()
                .planId(planId)
                .traceId(traceId)
                .farmId("farm-a")
                .targetAssetId("pump-a")
                .actionCategory("irrigation")
                .actionType("start")
                .commandId(commandId)
                .build());

        auditLogRepository.save(AuditLog.builder()
                .traceId(traceId)
                .eventType(AuditLog.EventType.PLAN_CREATED)
                .entityType("plan")
                .entityId(planId)
                .actor("system")
                .action("Plan created")
                .timestamp(base)
                .build());
        auditLogRepository.save(AuditLog.builder()
                .traceId(traceId)
                .eventType(AuditLog.EventType.COMMAND_TIMEOUT)
                .entityType("command")
                .entityId(commandId)
                .actor("system")
                .action("Command timeout")
                .timestamp(base.plusSeconds(10))
                .success(false)
                .build());
        auditLogRepository.save(AuditLog.builder()
                .traceId(traceId)
                .eventType(AuditLog.EventType.COMMAND_EXECUTED)
                .entityType("command")
                .entityId(commandId)
                .actor("terra-sense")
                .action("Device feedback: EXECUTED")
                .timestamp(base.plusSeconds(20))
                .build());
        auditLogRepository.save(AuditLog.builder()
                .traceId("trace-other")
                .eventType(AuditLog.EventType.COMMAND_EXECUTED)
                .entityType("command")
                .entityId("cmd-other")
                .actor("terra-sense")
                .action("Unrelated command")
                .timestamp(base.plusSeconds(15))
                .build());
        auditLogRepository.flush();

        List<AuditLog> history = auditLogRepository.findPlanHistory(planId);

        assertThat(history)
                .extracting(AuditLog::getEventType)
                .containsExactly(
                        AuditLog.EventType.PLAN_CREATED,
                        AuditLog.EventType.COMMAND_TIMEOUT,
                        AuditLog.EventType.COMMAND_EXECUTED);
        assertThat(history)
                .extracting(AuditLog::getEntityId)
                .containsExactly(planId, commandId, commandId)
                .doesNotContain("cmd-other");
    }
}
