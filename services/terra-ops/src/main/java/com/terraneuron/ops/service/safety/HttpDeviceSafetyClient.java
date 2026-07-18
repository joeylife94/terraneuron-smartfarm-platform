package com.terraneuron.ops.service.safety;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.entity.ActionPlan;
import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.MeterRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.HttpTimeoutException;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;

/** HTTP implementation of the Terra-Ops -> Terra-Sense safety boundary. */
@Slf4j
@Component
public class HttpDeviceSafetyClient implements DeviceSafetyClient {

    private final ObjectMapper objectMapper;
    private final SenseServiceJwtProvider jwtProvider;
    private final MeterRegistry meterRegistry;
    private final HttpClient httpClient;
    private final URI endpoint;
    private final Duration readTimeout;

    public HttpDeviceSafetyClient(
            ObjectMapper objectMapper,
            SenseServiceJwtProvider jwtProvider,
            MeterRegistry meterRegistry,
            @Value("${device-safety.client.base-url:http://localhost:8081}") String baseUrl,
            @Value("${device-safety.client.connect-timeout-ms:500}") long connectTimeoutMs,
            @Value("${device-safety.client.read-timeout-ms:1000}") long readTimeoutMs) {
        if (connectTimeoutMs <= 0 || readTimeoutMs <= 0) {
            throw new IllegalArgumentException("Device safety HTTP timeouts must be positive");
        }
        this.objectMapper = objectMapper;
        this.jwtProvider = jwtProvider;
        this.meterRegistry = meterRegistry;
        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(connectTimeoutMs))
                .build();
        this.endpoint = URI.create(stripTrailingSlash(baseUrl) + "/internal/device-safety/evaluate");
        this.readTimeout = Duration.ofMillis(readTimeoutMs);
    }

    @Override
    public DeviceSafetyResult evaluate(ActionPlan plan) {
        try {
            Map<String, Object> requestBody = new LinkedHashMap<>();
            requestBody.put("farmId", plan.getFarmId());
            requestBody.put("assetId", plan.getTargetAssetId());
            requestBody.put("actionCategory", plan.getActionCategory());
            requestBody.put("actionType", plan.getActionType());
            requestBody.put("parameters", parseParameters(plan.getParameters()));

            HttpRequest request = HttpRequest.newBuilder(endpoint)
                    .timeout(readTimeout)
                    .header("Authorization", "Bearer " + jwtProvider.createToken())
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(requestBody)))
                    .build();

            HttpResponse<String> response = httpClient.send(
                    request, HttpResponse.BodyHandlers.ofString());
            DeviceSafetyResult result = mapResponse(response);
            record(result.reasonCode());
            return result;
        } catch (HttpTimeoutException ex) {
            return blocked("SENSE_TIMEOUT");
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            return blocked("SENSE_TIMEOUT");
        } catch (IOException ex) {
            return blocked("SENSE_UNAVAILABLE");
        } catch (Exception ex) {
            log.warn("Terra-Sense safety evaluation failed closed: {}",
                    ex.getClass().getSimpleName());
            return blocked("SENSE_ERROR");
        }
    }

    private DeviceSafetyResult mapResponse(HttpResponse<String> response) {
        int status = response.statusCode();
        if (status == 401 || status == 403) {
            return DeviceSafetyResult.blocked("SENSE_AUTH_FAILED");
        }
        if (status >= 500) {
            return DeviceSafetyResult.blocked("SENSE_UNAVAILABLE");
        }
        if (status < 200 || status >= 300) {
            return DeviceSafetyResult.blocked("SENSE_ERROR");
        }

        try {
            SenseDecision decision = objectMapper.readValue(response.body(), SenseDecision.class);
            if (decision.reasonCode() == null || decision.reasonCode().isBlank()) {
                return DeviceSafetyResult.blocked("SENSE_MALFORMED_RESPONSE");
            }
            return decision.allowed()
                    ? DeviceSafetyResult.allow()
                    : DeviceSafetyResult.blocked(decision.reasonCode());
        } catch (Exception ex) {
            return DeviceSafetyResult.blocked("SENSE_MALFORMED_RESPONSE");
        }
    }

    private Map<String, Object> parseParameters(String parameters) throws IOException {
        if (parameters == null || parameters.isBlank()) {
            return Map.of();
        }
        return objectMapper.readValue(parameters, new TypeReference<Map<String, Object>>() { });
    }

    private DeviceSafetyResult blocked(String reason) {
        record(reason);
        return DeviceSafetyResult.blocked(reason);
    }

    private void record(String reason) {
        Counter.builder("terra_device_safety_sense_api_requests_total")
                .description("Terra-Ops device safety API outcomes by bounded reason")
                .tag("reason", reason.toLowerCase(Locale.ROOT))
                .register(meterRegistry)
                .increment();
    }

    private String stripTrailingSlash(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Terra-Sense base URL is required");
        }
        return value.endsWith("/") ? value.substring(0, value.length() - 1) : value;
    }

    private record SenseDecision(boolean allowed, String reasonCode) { }
}
