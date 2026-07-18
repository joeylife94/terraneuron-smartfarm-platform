package com.terraneuron.sense.controller;

import com.terraneuron.sense.model.SensorData;
import com.terraneuron.sense.security.DeviceSafetyServiceJwtFilter;
import com.terraneuron.sense.service.InfluxDbWriterService;
import com.terraneuron.sense.service.KafkaProducerService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(IngestionController.class)
class IngestionControllerValidationTest {

    @Autowired private MockMvc mockMvc;
    @MockBean private KafkaProducerService kafkaProducerService;
    @MockBean private InfluxDbWriterService influxDbWriterService;

    // This slice verifies ingestion validation, not the independent internal service-auth boundary.
    @MockBean private DeviceSafetyServiceJwtFilter deviceSafetyServiceJwtFilter;

    @Test
    void validSensorPayloadIsAccepted() throws Exception {
        mockMvc.perform(post("/api/v1/ingest/sensor-data")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "sensorId": "sensor-temp-01",
                                  "sensorType": "temperature",
                                  "value": 25.5,
                                  "unit": "°C",
                                  "farmId": "farm-A"
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("accepted"))
                .andExpect(jsonPath("$.sensorId").value("sensor-temp-01"));
        verify(influxDbWriterService).writeSensorData(any(SensorData.class));
        verify(kafkaProducerService).sendSensorData(any(SensorData.class));
    }

    @Test
    void missingSensorIdentityIsRejectedBeforeSideEffects() throws Exception {
        assertBadRequest("""
                {
                  "sensorType": "temperature",
                  "value": 25.5,
                  "unit": "°C",
                  "farmId": "farm-A"
                }
                """);
    }

    @Test
    void unsupportedSensorTypeIsRejectedBeforeSideEffects() throws Exception {
        assertBadRequest("""
                {
                  "sensorId": "sensor-unknown-01",
                  "sensorType": "pressure",
                  "value": 1013.2,
                  "unit": "hPa",
                  "farmId": "farm-A"
                }
                """);
    }

    @Test
    void physicallyImpossibleValueIsRejectedBeforeSideEffects() throws Exception {
        assertBadRequest("""
                {
                  "sensorId": "sensor-humidity-01",
                  "sensorType": "humidity",
                  "value": 140.0,
                  "unit": "%",
                  "farmId": "farm-A"
                }
                """);
    }

    @Test
    void excessiveFutureTimestampIsRejectedBeforeSideEffects() throws Exception {
        String futureTimestamp = Instant.now().plusSeconds(600).toString();
        assertBadRequest("""
                {
                  "sensorId": "sensor-temp-01",
                  "sensorType": "temperature",
                  "value": 25.5,
                  "unit": "°C",
                  "farmId": "farm-A",
                  "timestamp": "%s"
                }
                """.formatted(futureTimestamp));
    }

    private void assertBadRequest(String payload) throws Exception {
        mockMvc.perform(post("/api/v1/ingest/sensor-data")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(payload))
                .andExpect(status().isBadRequest());
        verifyNoInteractions(influxDbWriterService, kafkaProducerService);
    }
}
