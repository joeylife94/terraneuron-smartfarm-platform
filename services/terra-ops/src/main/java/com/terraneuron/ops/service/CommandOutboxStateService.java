package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.entity.CommandOutboxEvent;
import com.terraneuron.ops.repository.ActionPlanRepository;
import com.terraneuron.ops.repository.CommandOutboxRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Duration;
import java.time.Instant;
import java.util.List;

/** Transactional state transitions used by the asynchronous outbox publisher. */
@Service
@RequiredArgsConstructor
public class CommandOutboxStateService {

    private final CommandOutboxRepository commandOutboxRepository;
    private final ActionPlanRepository actionPlanRepository;
    private final AuditService auditService;

    @Transactional(readOnly = true)
    public List<CommandOutboxEvent> findReady(Instant now) {
        return commandOutboxRepository
                .findTop50ByStatusAndNextAttemptAtLessThanEqualOrderByCreatedAtAsc(
                        CommandOutboxEvent.OutboxStatus.PENDING,
                        now);
    }

    @Transactional
    public boolean claim(Long eventId, Instant now) {
        return commandOutboxRepository.claimForPublication(
                eventId,
                CommandOutboxEvent.OutboxStatus.PENDING,
                CommandOutboxEvent.OutboxStatus.PROCESSING,
                now) == 1;
    }

    @Transactional
    public int recoverStaleClaims(Instant now, Duration lockTimeout) {
        return commandOutboxRepository.recoverStaleClaims(
                CommandOutboxEvent.OutboxStatus.PROCESSING,
                CommandOutboxEvent.OutboxStatus.PENDING,
                now.minus(lockTimeout),
                now);
    }

    @Transactional(readOnly = true)
    public CommandOutboxEvent getRequired(Long eventId) {
        return commandOutboxRepository.findById(eventId)
                .orElseThrow(() -> new IllegalStateException("Outbox event not found: " + eventId));
    }

    @Transactional
    public void markPublished(Long eventId, Instant publishedAt) {
        CommandOutboxEvent event = commandOutboxRepository.findById(eventId)
                .orElseThrow(() -> new IllegalStateException("Outbox event not found: " + eventId));

        event.setStatus(CommandOutboxEvent.OutboxStatus.PUBLISHED);
        event.setPublishedAt(publishedAt);
        event.setLockedAt(null);
        event.setLastError(null);
        commandOutboxRepository.save(event);

        ActionPlan plan = actionPlanRepository.findByCommandId(event.getCommandId())
                .orElseThrow(() -> new IllegalStateException(
                        "Action plan not found for command: " + event.getCommandId()));

        // Feedback may already have advanced the plan. Never regress a later state.
        if (plan.getStatus() == ActionPlan.PlanStatus.DISPATCHING) {
            plan.setStatus(ActionPlan.PlanStatus.DISPATCHED);
            plan.setDispatchedAt(publishedAt);
            plan.setExecutionResult("KAFKA_ACKNOWLEDGED");
            plan.setExecutionError(null);
            actionPlanRepository.save(plan);
        } else if (plan.getDispatchedAt() == null) {
            plan.setDispatchedAt(publishedAt);
            actionPlanRepository.save(plan);
        }
    }

    @Transactional
    public void markFailed(
            Long eventId,
            String error,
            Instant failedAt,
            int maxAttempts,
            Duration baseBackoff) {
        CommandOutboxEvent event = commandOutboxRepository.findById(eventId)
                .orElseThrow(() -> new IllegalStateException("Outbox event not found: " + eventId));

        int attempts = event.getAttempts() + 1;
        event.setAttempts(attempts);
        event.setLockedAt(null);
        event.setLastError(error);

        ActionPlan plan = actionPlanRepository.findByCommandId(event.getCommandId())
                .orElseThrow(() -> new IllegalStateException(
                        "Action plan not found for command: " + event.getCommandId()));

        if (attempts >= maxAttempts) {
            event.setStatus(CommandOutboxEvent.OutboxStatus.DEAD);
            event.setNextAttemptAt(failedAt);
            commandOutboxRepository.save(event);

            if (plan.getStatus() == ActionPlan.PlanStatus.DISPATCHING) {
                plan.setStatus(ActionPlan.PlanStatus.DISPATCH_FAILED);
                plan.setExecutionResult("OUTBOX_DEAD_LETTER");
                plan.setExecutionError(error);
                actionPlanRepository.save(plan);
                auditService.logCommandExecuted(plan, false, null, error);
            }
            return;
        }

        long multiplier = 1L << Math.min(attempts - 1, 10);
        Duration delay = baseBackoff.multipliedBy(multiplier);
        Duration cappedDelay = delay.compareTo(Duration.ofMinutes(5)) > 0
                ? Duration.ofMinutes(5)
                : delay;

        event.setStatus(CommandOutboxEvent.OutboxStatus.PENDING);
        event.setNextAttemptAt(failedAt.plus(cappedDelay));
        commandOutboxRepository.save(event);

        if (plan.getStatus() == ActionPlan.PlanStatus.DISPATCHING) {
            plan.setExecutionResult("KAFKA_RETRY_PENDING");
            plan.setExecutionError(error);
            actionPlanRepository.save(plan);
        }
    }
}
