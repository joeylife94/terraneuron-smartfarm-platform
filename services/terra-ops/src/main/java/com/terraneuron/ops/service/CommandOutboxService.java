package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.CommandOutboxEvent;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.repository.CommandOutboxRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/** Creates a command and its outbox record in the caller's database transaction. */
@Service
@RequiredArgsConstructor
public class CommandOutboxService {
    static final String COMMAND_TOPIC = "terra.control.command";

    private final ActionPlanRepository actionPlanRepository;
    private final CommandOutboxRepository commandOutboxRepository;
    private final ObjectMapper objectMapper;

    @Transactional(propagation = Propagation.MANDATORY)
    public CommandOutboxEvent enqueue(ActionPlan plan) {
        if (plan == null || !plan.canBeDispatched()) {
            throw new IllegalStateException("Only an approved, non-expired plan can be enqueued");
        }
        if (plan.getCommandId() != null && !plan.getCommandId().isBlank()) {
            throw new IllegalStateException("Plan already owns a command and cannot be enqueued again");
        }

        String commandId = "cmd-" + UUID.randomUUID();
        Instant now = Instant.now();
        Map<String, Object> commandEvent = buildCommandEvent(plan, commandId, now);

        plan.setCommandId(commandId);
        plan.setStatus(ActionPlan.PlanStatus.DISPATCHING);
        plan.setExecutionResult("COMMAND_OUTBOX_PENDING");
        plan.setExecutionError(null);
        plan.setDispatchedAt(null);
        plan.setDeliveredAt(null);
        plan.setAckDeadlineAt(null);
        plan.setExecutedAt(null);
        actionPlanRepository.save(plan);

        try {
            CommandOutboxEvent outboxEvent = CommandOutboxEvent.builder()
                    .eventId(UUID.randomUUID().toString())
                    .planId(plan.getPlanId())
                    .commandId(commandId)
                    .topic(COMMAND_TOPIC)
                    .messageKey(plan.getFarmId())
                    .payload(objectMapper.writeValueAsString(commandEvent))
                    .status(CommandOutboxEvent.OutboxStatus.PENDING)
                    .attempts(0)
                    .nextAttemptAt(now)
                    .build();
            return commandOutboxRepository.save(outboxEvent);
        } catch (JsonProcessingException e) {
            throw new IllegalStateException("Failed to serialize command outbox payload", e);
        }
    }

    private Map<String, Object> buildCommandEvent(ActionPlan plan, String commandId, Instant now) {
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("trace_id", plan.getTraceId());
        data.put("plan_id", plan.getPlanId());
        data.put("command_id", commandId);
        data.put("farm_id", plan.getFarmId());
        data.put("target_asset_id", plan.getTargetAssetId());
        data.put("target_asset_type", plan.getTargetAssetType());
        data.put("action_category", plan.getActionCategory());
        data.put("action_type", plan.getActionType());
        data.put("parameters", parseParameters(plan.getParameters()));
        data.put("executed_by", plan.getApprovedBy());

        Map<String, Object> event = new LinkedHashMap<>();
        event.put("specversion", "1.0");
        event.put("type", "terra.ops.command.execute");
        event.put("source", "//terraneuron/terra-ops");
        event.put("id", UUID.randomUUID().toString());
        event.put("time", now.toString());
        event.put("datacontenttype", "application/json");
        event.put("data", data);
        return event;
    }

    private Map<String, Object> parseParameters(String parametersJson) {
        if (parametersJson == null || parametersJson.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(
                    parametersJson,
                    new TypeReference<Map<String, Object>>() { });
        } catch (JsonProcessingException e) {
            throw new IllegalArgumentException("Invalid command parameters JSON", e);
        }
    }
}