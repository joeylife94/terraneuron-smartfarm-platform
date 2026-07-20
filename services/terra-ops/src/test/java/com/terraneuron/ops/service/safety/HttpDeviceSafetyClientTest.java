package com.terraneuron.ops.service.safety;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import com.terraneuron.ops.entity.ActionPlan;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class HttpDeviceSafetyClientTest {

    private static final Instant NOW = Instant.parse("2026-07-18T03:00:00Z");
    private static final String SECRET = "test-device-safety-secret-key-32-bytes-minimum";

    private HttpServer server;
    private AtomicReference<Response> response;
    private HttpDeviceSafetyClient client;

    @BeforeEach
    void setUp() throws Exception {
        response = new AtomicReference<>(new Response(
                200, "{\"allowed\":true,\"reasonCode\":\"ALLOWED\"}", 0));
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/internal/device-safety/evaluate", this::handle);
        server.start();

        SenseServiceJwtProvider jwtProvider = new SenseServiceJwtProvider(
                Clock.fixed(NOW, ZoneOffset.UTC));
        ReflectionTestUtils.setField(jwtProvider, "secret", SECRET);
        ReflectionTestUtils.setField(jwtProvider, "issuer", "terraneuron-internal");
        ReflectionTestUtils.setField(jwtProvider, "subject", "terra-ops");
        ReflectionTestUtils.setField(jwtProvider, "audience", "terra-sense");
        ReflectionTestUtils.setField(jwtProvider, "scope", "device:safety:evaluate");
        ReflectionTestUtils.setField(jwtProvider, "lifetimeSeconds", 30L);
        jwtProvider.validateConfiguration();

        client = new HttpDeviceSafetyClient(
                new ObjectMapper(),
                jwtProvider,
                new SimpleMeterRegistry(),
                "http://127.0.0.1:" + server.getAddress().getPort(),
                100,
                100);
    }

    @AfterEach
    void stopServer() {
        server.stop(0);
    }

    @Test
    void validResponseAllowsCommand() {
        assertThat(client.evaluate(plan()).allowed()).isTrue();
    }

    @Test
    void authFailureFailsClosed() {
        response.set(new Response(401, "", 0));
        assertBlocked("SENSE_AUTH_FAILED");
    }

    @Test
    void serverFailureFailsClosed() {
        response.set(new Response(503, "", 0));
        assertBlocked("SENSE_UNAVAILABLE");
    }

    @Test
    void malformedResponseFailsClosed() {
        response.set(new Response(200, "not-json", 0));
        assertBlocked("SENSE_MALFORMED_RESPONSE");
    }

    @Test
    void unknownReasonCodeCannotCreateUnboundedMetricsOrAuditValues() {
        response.set(new Response(
                200,
                "{\"allowed\":false,\"reasonCode\":\"asset-fan-01-private-detail\"}",
                0));
        assertBlocked("SENSE_MALFORMED_RESPONSE");
    }

    @Test
    void allowedFlagAndReasonMustAgree() {
        response.set(new Response(
                200,
                "{\"allowed\":true,\"reasonCode\":\"STATE_OFFLINE\"}",
                0));
        assertBlocked("SENSE_MALFORMED_RESPONSE");
    }

    @Test
    void timeoutFailsClosed() {
        response.set(new Response(
                200, "{\"allowed\":true,\"reasonCode\":\"ALLOWED\"}", 250));
        assertBlocked("SENSE_TIMEOUT");
    }

    private void assertBlocked(String reason) {
        DeviceSafetyClient.DeviceSafetyResult result = client.evaluate(plan());
        assertThat(result.allowed()).isFalse();
        assertThat(result.reasonCode()).isEqualTo(reason);
    }

    private ActionPlan plan() {
        return ActionPlan.builder()
                .farmId("farm-1")
                .targetAssetId("fan-01")
                .targetAssetType("device")
                .actionCategory("ventilation")
                .actionType("turn_on")
                .parameters("{\"speed_level\":\"high\"}")
                .build();
    }

    private void handle(HttpExchange exchange) throws IOException {
        Response current = response.get();
        if (current.delayMillis() > 0) {
            try {
                Thread.sleep(current.delayMillis());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        }
        byte[] body = current.body().getBytes(StandardCharsets.UTF_8);
        try {
            exchange.sendResponseHeaders(current.status(), body.length);
            exchange.getResponseBody().write(body);
        } catch (IOException ignored) {
            // Expected when the client timeout closes the exchange.
        } finally {
            exchange.close();
        }
    }

    private record Response(int status, String body, long delayMillis) { }
}
