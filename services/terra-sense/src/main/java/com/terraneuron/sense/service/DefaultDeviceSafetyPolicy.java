package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyReason;
import com.terraneuron.sense.model.DeviceSafetyRequest;
import com.terraneuron.sense.model.DeviceStateRecord;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.Optional;

/** Shared fail-closed policy used by the internal API and MQTT pre-dispatch recheck. */
@Service
public class DefaultDeviceSafetyPolicy implements DeviceSafetyPolicy {

    private final DeviceStateRegistry registry;
    private final List<DeviceCapabilityResolver> capabilityResolvers;
    private final MeterRegistry meterRegistry;
    private final Clock clock;
    private final Duration freshness;
    private final Duration reportedFutureSkew;

    public DefaultDeviceSafetyPolicy(
            DeviceStateRegistry registry,
            List<DeviceCapabilityResolver> capabilityResolvers,
            MeterRegistry meterRegistry,
            Clock clock,
            @Value("${app.device-state.freshness-seconds:120}") long freshnessSeconds,
            @Value("${app.device-state.registry.ttl-seconds:600}") long registryTtlSeconds,
            @Value("${app.device-state.reported-future-skew-seconds:10}") long reportedFutureSkewSeconds) {
        if (freshnessSeconds <= 0 || reportedFutureSkewSeconds < 0) {
            throw new IllegalArgumentException("Device safety time windows are invalid");
        }
        if (registryTtlSeconds <= freshnessSeconds) {
            throw new IllegalArgumentException(
                    "Device state registry TTL must be greater than the freshness window");
        }
        this.registry = registry;
        this.capabilityResolvers = List.copyOf(capabilityResolvers);
        this.meterRegistry = meterRegistry;
        this.clock = clock;
        this.freshness = Duration.ofSeconds(freshnessSeconds);
        this.reportedFutureSkew = Duration.ofSeconds(reportedFutureSkewSeconds);

        Gauge.builder("terra_device_safety_freshness_seconds", freshness, Duration::toSeconds)
                .description("Maximum age accepted by the device safety gate")
                .register(meterRegistry);
    }

    @Override
    public DeviceSafetyDecision evaluate(DeviceSafetyRequest request) {
        Instant now = clock.instant();
        if (request == null || isBlank(request.farmId()) || isBlank(request.assetId())) {
            return blocked(DeviceSafetyReason.IDENTITY_MISMATCH, now, null, null);
        }

        final Optional<DeviceStateRecord> stateResult;
        try {
            stateResult = registry.find(request.farmId(), request.assetId());
        } catch (DeviceStateRegistryUnavailableException ex) {
            return blocked(DeviceSafetyReason.REGISTRY_UNAVAILABLE, now, null, null);
        }

        if (stateResult.isEmpty()) {
            return blocked(DeviceSafetyReason.STATE_MISSING, now, null, null);
        }

        DeviceStateRecord state = stateResult.get();
        if (!request.farmId().equals(state.getFarmId())
                || !request.assetId().equals(state.getAssetId())) {
            return blocked(DeviceSafetyReason.IDENTITY_MISMATCH, now, null, null);
        }

        Long observedAge = ageSeconds(state.getObservedAt(), now);
        Long reportedAge = ageSeconds(state.getReportedAt(), now);

        if (state.getObservedAt() == null || observedAge == null || observedAge > freshness.toSeconds()) {
            return blocked(DeviceSafetyReason.STATE_STALE, now, observedAge, reportedAge);
        }
        if (state.getReportedAt() == null) {
            return blocked(DeviceSafetyReason.REPORTED_STATE_STALE, now, observedAge, null);
        }
        if (state.getReportedAt().isAfter(now.plus(reportedFutureSkew))) {
            return blocked(DeviceSafetyReason.REPORTED_TIME_INVALID, now, observedAge, reportedAge);
        }
        if (reportedAge == null || reportedAge > freshness.toSeconds()) {
            return blocked(DeviceSafetyReason.REPORTED_STATE_STALE, now, observedAge, reportedAge);
        }

        if (state.isMaintenanceMode()) {
            return blocked(DeviceSafetyReason.MAINTENANCE_MODE, now, observedAge, reportedAge);
        }

        String normalizedState = normalize(state.getState());
        switch (normalizedState) {
            case "online", "running", "idle" -> {
                // Continue with capability checks.
            }
            case "offline" -> {
                return blocked(DeviceSafetyReason.STATE_OFFLINE, now, observedAge, reportedAge);
            }
            case "error" -> {
                return blocked(DeviceSafetyReason.STATE_ERROR, now, observedAge, reportedAge);
            }
            default -> {
                return blocked(DeviceSafetyReason.STATE_UNKNOWN, now, observedAge, reportedAge);
            }
        }

        Optional<DeviceCapabilityResolver.DeviceCapabilities> capabilities = capabilityResolvers.stream()
                .map(resolver -> resolver.resolve(state))
                .flatMap(Optional::stream)
                .findFirst();
        if (capabilities.isEmpty()) {
            return blocked(DeviceSafetyReason.UNSUPPORTED_DEVICE_TYPE, now, observedAge, reportedAge);
        }

        DeviceCapabilityResolver.DeviceCapabilities resolved = capabilities.get();
        String category = resolveCategory(request.actionCategory(), resolved);
        String action = normalize(request.actionType());

        if (!resolved.actionCategories().contains(category)) {
            return blocked(DeviceSafetyReason.ACTION_CATEGORY_MISMATCH, now, observedAge, reportedAge);
        }
        if (!resolved.actionTypes().contains(action)) {
            return blocked(DeviceSafetyReason.ACTION_UNSUPPORTED, now, observedAge, reportedAge);
        }
        if ("adjust".equals(action)) {
            boolean hasSupportedParameter = request.parameters() != null
                    && resolved.adjustParameterAnyOf().stream().anyMatch(request.parameters()::containsKey);
            if (!hasSupportedParameter) {
                return blocked(DeviceSafetyReason.ADJUST_PARAMETERS_MISSING, now, observedAge, reportedAge);
            }
        }

        DeviceSafetyDecision decision = DeviceSafetyDecision.allowed(now, observedAge, reportedAge);
        record(decision);
        return decision;
    }

    private String resolveCategory(
            String requestedCategory,
            DeviceCapabilityResolver.DeviceCapabilities capabilities) {
        String normalized = normalize(requestedCategory);
        if (!normalized.isBlank()) {
            return normalized;
        }
        // Pre-safety-rollout outbox rows did not carry action_category. A legacy
        // command is accepted only when the explicit device capability resolves
        // to exactly one category; ambiguous adapters remain fail-closed.
        return capabilities.actionCategories().size() == 1
                ? capabilities.actionCategories().iterator().next()
                : "";
    }

    private DeviceSafetyDecision blocked(
            DeviceSafetyReason reason,
            Instant now,
            Long observedAge,
            Long reportedAge) {
        DeviceSafetyDecision decision = DeviceSafetyDecision.blocked(
                reason, now, observedAge, reportedAge);
        record(decision);
        return decision;
    }

    private void record(DeviceSafetyDecision decision) {
        Counter.builder("terra_device_safety_evaluations_total")
                .description("Device safety evaluations by bounded outcome and reason")
                .tag("outcome", decision.allowed() ? "allowed" : "blocked")
                .tag("reason", decision.reasonCode().name().toLowerCase(Locale.ROOT))
                .register(meterRegistry)
                .increment();
    }

    private Long ageSeconds(Instant timestamp, Instant now) {
        if (timestamp == null) {
            return null;
        }
        return Math.max(0L, Duration.between(timestamp, now).getSeconds());
    }

    private String normalize(String value) {
        return value == null ? "" : value.trim().toLowerCase(Locale.ROOT);
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
