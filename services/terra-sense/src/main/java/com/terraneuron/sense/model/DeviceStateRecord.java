package com.terraneuron.sense.model;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/**
 * Shared device state stored by Terra-Sense.
 *
 * {@code reportedAt} is supplied by the device. {@code observedAt} is assigned by
 * Terra-Sense when the MQTT message is accepted, so device clock drift and transport
 * freshness can be evaluated independently.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DeviceStateRecord {

    private String farmId;
    private String assetId;
    private String deviceType;
    private String state;

    @Builder.Default
    private boolean maintenanceMode = false;

    @Builder.Default
    private Set<String> capabilities = new LinkedHashSet<>();

    @Builder.Default
    private Map<String, Object> attributes = new LinkedHashMap<>();

    /** Latest command acknowledgement reported by the device, when present. */
    private String lastCommandId;
    private String lastCommandStatus;
    private String lastCommandError;

    private Instant reportedAt;
    private Instant observedAt;

    public static DeviceStateRecord from(DeviceStatus status, Instant observedAt) {
        return DeviceStateRecord.builder()
                .farmId(status.getFarmId())
                .assetId(status.getAssetId())
                .deviceType(status.getDeviceType())
                .state(status.getState())
                .maintenanceMode(Boolean.TRUE.equals(status.getMaintenanceMode()))
                .capabilities(status.getCapabilities() != null
                        ? new LinkedHashSet<>(status.getCapabilities())
                        : new LinkedHashSet<>())
                .attributes(status.getAttributes() != null
                        ? new LinkedHashMap<>(status.getAttributes())
                        : new LinkedHashMap<>())
                .lastCommandId(status.getLastCommandId())
                .lastCommandStatus(status.getLastCommandStatus())
                .lastCommandError(status.getLastCommandError())
                .reportedAt(status.getReportedAt())
                .observedAt(observedAt)
                .build();
    }
}
