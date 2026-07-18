package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceStateRecord;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.stereotype.Component;

import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/**
 * Conservative capability table for generic device types.
 * Matching is exact after normalization; asset identifiers are never inspected.
 */
@Component
@Order(Ordered.LOWEST_PRECEDENCE)
public class DefaultDeviceCapabilityResolver implements DeviceCapabilityResolver {

    private static final Set<String> SWITCH_AND_ADJUST = Set.of("turn_on", "turn_off", "adjust");

    private static final Map<String, DeviceCapabilities> CAPABILITIES = Map.ofEntries(
            Map.entry("fan", capabilities("ventilation", Set.of("speed_level", "power_percentage"))),
            Map.entry("vent", capabilities("ventilation", Set.of("position_percentage"))),
            Map.entry("pump", capabilities("irrigation", Set.of("flow_rate", "duration_minutes"))),
            Map.entry("valve", capabilities("irrigation", Set.of("position_percentage", "duration_minutes"))),
            Map.entry("humidifier", capabilities("irrigation", Set.of("target_humidity", "power_percentage"))),
            Map.entry("heater", capabilities("heating", Set.of("target_temperature", "power_percentage"))),
            Map.entry("cooler", capabilities("cooling", Set.of("target_temperature", "power_percentage"))),
            Map.entry("dehumidifier", capabilities("cooling", Set.of("target_humidity", "power_percentage"))),
            Map.entry("led", capabilities("lighting", Set.of("brightness_percentage", "duration_minutes"))),
            Map.entry("light", capabilities("lighting", Set.of("brightness_percentage", "duration_minutes")))
    );

    @Override
    public Optional<DeviceCapabilities> resolve(DeviceStateRecord state) {
        if (state == null || state.getDeviceType() == null || state.getDeviceType().isBlank()) {
            return Optional.empty();
        }
        return Optional.ofNullable(CAPABILITIES.get(normalize(state.getDeviceType())));
    }

    private static DeviceCapabilities capabilities(String category, Set<String> adjustParameters) {
        return new DeviceCapabilities(Set.of(category), SWITCH_AND_ADJUST, adjustParameters);
    }

    private static String normalize(String value) {
        return value.trim().toLowerCase(Locale.ROOT);
    }
}