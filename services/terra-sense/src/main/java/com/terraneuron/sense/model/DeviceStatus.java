package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

/**
 * Device status reported over MQTT.
 *
 * A device confirms a command by sending lastCommandId together with
 * lastCommandStatus=EXECUTED or FAILED. Generic online/running/idle state is
 * never interpreted as command execution acknowledgement.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DeviceStatus {

    /** Device/asset ID */
    private String assetId;

    /** Farm ID */
    private String farmId;

    /** Explicit device type used by capability policy; asset IDs are never inspected. */
    private String deviceType;

    /** Current device state (online, offline, running, idle, error, unknown) */
    private String state;

    /** Device-reported maintenance mode. */
    @Builder.Default
    private Boolean maintenanceMode = false;

    /** Optional adapter-specific capability identifiers. */
    private Set<String> capabilities;

    /** Last command ID handled by the physical device */
    private String lastCommandId;

    /** Explicit command outcome: EXECUTED or FAILED */
    private String lastCommandStatus;

    /** Device-reported command failure detail */
    private String lastCommandError;

    /** Extended properties (speed_level, power_percentage, etc.) */
    private Map<String, Object> attributes;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")
    private Instant reportedAt;

    public boolean isOnline() {
        return "online".equalsIgnoreCase(state)
                || "running".equalsIgnoreCase(state)
                || "idle".equalsIgnoreCase(state);
    }

    public boolean hasTerminalCommandAcknowledgement() {
        return lastCommandId != null
                && !lastCommandId.isBlank()
                && ("EXECUTED".equalsIgnoreCase(lastCommandStatus)
                    || "FAILED".equalsIgnoreCase(lastCommandStatus));
    }
}