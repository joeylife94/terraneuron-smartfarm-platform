package com.terraneuron.ops.security;

import com.terraneuron.ops.controller.CropController;
import com.terraneuron.ops.service.CropService;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Date;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = CropController.class)
@Import({
        SecurityConfig.class,
        JwtAuthenticationFilter.class,
        JwtTokenProvider.class,
        ServiceJwtAuthenticationFilter.class
})
@TestPropertySource(properties = {
        "jwt.secret=TEST_ONLY_CHANGE_ME_LOCAL_JWT_SECRET_32_CHARS",
        "service-auth.jwt.secret=TEST_ONLY_CHANGE_ME_SERVICE_JWT_SECRET_32_CHARS",
        "service-auth.jwt.issuer=terraneuron-internal",
        "service-auth.jwt.audience=terra-ops",
        "service-auth.jwt.allowed-subject=terra-cortex",
        "app.cors.allowed-origins=http://localhost:3000"
})
class ServiceAuthSecurityTest {

    private static final String SERVICE_SECRET =
            "TEST_ONLY_CHANGE_ME_SERVICE_JWT_SECRET_32_CHARS";

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private CropService cropService;

    @Test
    void validScopedServiceTokenCanReadOptimalConditions() throws Exception {
        when(cropService.getOptimalConditions("farm-A"))
                .thenReturn(Map.of("hasCropProfile", true));

        mockMvc.perform(get("/api/farms/farm-A/optimal-conditions")
                        .header(HttpHeaders.AUTHORIZATION, bearer(serviceToken("crop:read", "terra-cortex", 60))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hasCropProfile").value(true));
    }

    @Test
    void missingOrWrongScopeServiceTokenIsRejected() throws Exception {
        assertRejected(mockMvc.perform(get("/api/farms/farm-A/optimal-conditions"))
                .andReturn().getResponse().getStatus());

        assertRejected(mockMvc.perform(get("/api/farms/farm-A/optimal-conditions")
                        .header(HttpHeaders.AUTHORIZATION, bearer(serviceToken("other:read", "terra-cortex", 60))))
                .andReturn().getResponse().getStatus());
    }

    @Test
    void expiredOrUnexpectedSubjectServiceTokenIsRejected() throws Exception {
        assertRejected(mockMvc.perform(get("/api/farms/farm-A/optimal-conditions")
                        .header(HttpHeaders.AUTHORIZATION, bearer(serviceToken("crop:read", "other-service", 60))))
                .andReturn().getResponse().getStatus());

        assertRejected(mockMvc.perform(get("/api/farms/farm-A/optimal-conditions")
                        .header(HttpHeaders.AUTHORIZATION, bearer(serviceToken("crop:read", "terra-cortex", -1))))
                .andReturn().getResponse().getStatus());
    }

    @Test
    void serviceTokenCannotAccessOtherAuthenticatedRoutes() throws Exception {
        int responseStatus = mockMvc.perform(get("/api/crops")
                        .header(HttpHeaders.AUTHORIZATION, bearer(serviceToken("crop:read", "terra-cortex", 60))))
                .andReturn()
                .getResponse()
                .getStatus();

        assertRejected(responseStatus);
    }

    private static String serviceToken(String scope, String subject, long expiresInSeconds) {
        Instant now = Instant.now();
        SecretKey key = Keys.hmacShaKeyFor(SERVICE_SECRET.getBytes(StandardCharsets.UTF_8));
        return Jwts.builder()
                .issuer("terraneuron-internal")
                .subject(subject)
                .claim("aud", "terra-ops")
                .claim("type", "service")
                .claim("scope", scope)
                .issuedAt(Date.from(now.minusSeconds(1)))
                .expiration(Date.from(now.plusSeconds(expiresInSeconds)))
                .signWith(key)
                .compact();
    }

    private static String bearer(String token) {
        return "Bearer " + token;
    }

    private static void assertRejected(int status) {
        assertThat(status).isIn(401, 403);
    }
}
