package com.terraneuron.sense.model;

import java.time.Instant;

/**
 * Non-sensitive safety decision returned internally and reused before MQTT dispatch.
 * No raw device payload or identifiers are included.
 */
public record DeviceSafetyDecision(
        boolean allowed,
        DeviceSafetyReason reasonCode,
        Instant evaluatedAt,
        Long observedAgeSeconds,
        Long reportedAgeSeconds
) {
    public static DeviceSafetyDecision allowed(Instant evaluatedAt, long observedAge, long reportedAge) {
        return new DeviceSafetyDecision(
                true,
                DeviceSafetyReason.ALLOWED,
                evaluatedAt,
                observedAge,
                reportedAge);
    }

    public static DeviceSafetyDecision allowedWithoutDeviceState(Instant evaluatedAt) {
        return new DeviceSafetyDecision(
                true,
                DeviceSafetyReason.ALLOWED,
                evaluatedAt,
                null,
                null);
    }

    public static DeviceSafetyDecision blocked(
            DeviceSafetyReason reasonCode,
            Instant evaluatedAt,
            Long observedAge,
            Long reportedAge) {
        return new DeviceSafetyDecision(false, reasonCode, evaluatedAt, observedAge, reportedAge);
    }
}
