package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceStateRecord;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Repository-owned synthetic adapter/model fixture used only for bounded software
 * conformance proof. It intentionally models no real manufacturer or hardware.
 *
 * <p>The explicit adapter marker claims the state for this resolver. Known models
 * receive their declared capabilities. Unknown models return an explicit empty
 * capability set so the generic fallback cannot accidentally admit them.</p>
 */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
public class SyntheticConformanceDeviceCapabilityResolver implements DeviceCapabilityResolver {

    public static final String ADAPTER_ATTRIBUTE = "adapterId";
    public static final String MODEL_ATTRIBUTE = "modelId";
    public static final String ADAPTER_ID = "terraneuron-synthetic-conformance-v1";
    public static final String MODEL_ID = "tn-synth-climate-01";

    private static final DeviceCapabilities KNOWN_MODEL_CAPABILITIES = new DeviceCapabilities(
            Set.of("heating"),
            Set.of("turn_on", "turn_off", "adjust"),
            Set.of("target_temperature"));

    private static final DeviceCapabilities FAIL_CLOSED_CAPABILITIES = new DeviceCapabilities(
            Set.of(), Set.of(), Set.of());

    @Override
    public Optional<DeviceCapabilities> resolve(DeviceStateRecord state) {
        if (state == null) {
            return Optional.empty();
        }
        Map<String, Object> attributes = state.getAttributes();
        if (attributes == null || !ADAPTER_ID.equals(String.valueOf(attributes.get(ADAPTER_ATTRIBUTE)))) {
            return Optional.empty();
        }

        if (MODEL_ID.equals(String.valueOf(attributes.get(MODEL_ATTRIBUTE)))) {
            return Optional.of(KNOWN_MODEL_CAPABILITIES);
        }

        // The explicit synthetic adapter marker owns unknown synthetic models and
        // must fail closed rather than falling through to generic deviceType rules.
        return Optional.of(FAIL_CLOSED_CAPABILITIES);
    }
}
