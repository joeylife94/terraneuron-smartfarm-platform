package com.terraneuron.sense.model;

import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

class SensorDataEventIdentityTest {

    @Test
    void sameMeasurementProducesSameCrossLanguageEventId() {
        SensorData first = measurement();
        SensorData second = measurement();

        assertThat(first.ensureEventId())
                .isEqualTo("evt-88ea9753f06c5b9e2f54fd4869938235134c892d56f90c0e038ee64281890fd1")
                .isEqualTo(second.ensureEventId());
    }

    @Test
    void suppliedEventIdIsPreserved() {
        SensorData sensorData = measurement();
        sensorData.setEventId("provider:station-1:observation-42");

        assertThat(sensorData.ensureEventId()).isEqualTo("provider:station-1:observation-42");
    }

    @Test
    void changedMeasurementProducesDifferentEventId() {
        SensorData first = measurement();
        SensorData second = measurement();
        second.setValue(31.6);

        assertThat(first.ensureEventId()).isNotEqualTo(second.ensureEventId());
    }

    private static SensorData measurement() {
        return SensorData.builder()
                .farmId("farm-1")
                .sensorId("sensor-1")
                .sensorType("temperature")
                .value(31.5)
                .unit("°C")
                .timestamp(Instant.parse("2026-07-16T00:00:00Z"))
                .build();
    }
}
