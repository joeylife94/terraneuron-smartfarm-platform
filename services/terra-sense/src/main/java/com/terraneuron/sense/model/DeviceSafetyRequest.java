package com.terraneuron.sense.model;

import java.util.Map;

/** Internal safety-evaluation request. */
public record DeviceSafetyRequest(
        String farmId,
        String assetId,
        String actionCategory,
        String actionType,
        Map<String, Object> parameters
) {
    public DeviceSafetyRequest {
        parameters = parameters == null ? Map.of() : Map.copyOf(parameters);
    }
}