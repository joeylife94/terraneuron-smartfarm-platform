package com.terraneuron.sense.model;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DeviceSafetyRequestTest {

    @Test
    void preservesNullValuedParametersInAnImmutableSnapshot() {
        Map<String, Object> input = new LinkedHashMap<>();
        input.put("target_value", null);

        DeviceSafetyRequest request = new DeviceSafetyRequest(
                "farm-1", "heater-01", "heating", "adjust", input);

        assertThat(request.parameters()).containsEntry("target_value", null);
        input.put("target_value", 25);
        assertThat(request.parameters()).containsEntry("target_value", null);
        assertThatThrownBy(() -> request.parameters().put("other", 1))
                .isInstanceOf(UnsupportedOperationException.class);
    }
}
