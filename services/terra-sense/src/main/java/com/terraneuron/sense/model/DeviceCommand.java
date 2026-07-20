package com.terraneuron.sense.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.Instant;
import java.util.Map;

/** Command authorized by Terra-Ops and delivered to a physical device through MQTT. */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class DeviceCommand {

    private String commandId;
    private String traceId;
    private String planId;
    private String targetAssetId;
    private String targetAssetType;
    private String actionCategory;
    private String actionType;
    private Map<String, Object> parameters;
    private String executedBy;
    private String farmId;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", timezone = "UTC")
    private Instant issuedAt;

    public String toMqttTopic() {
        return String.format("terra/devices/%s/%s/command",
                farmId != null ? farmId : "unknown",
                targetAssetId != null ? targetAssetId : "unknown"
        );
    }

    public String toFeedbackTopic() {
        return String.format("terra/devices/%s/%s/status",
                farmId != null ? farmId : "unknown",
                targetAssetId != null ? targetAssetId : "unknown"
        );
    }
}