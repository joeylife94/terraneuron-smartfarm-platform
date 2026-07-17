package com.terraneuron.ops.security;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.controller.ActionController;
import com.terraneuron.ops.controller.AuthController;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.service.ActionPlanService;
import com.terraneuron.ops.service.AuditService;
import com.terraneuron.ops.service.UserAuthenticationService;
import com.terraneuron.ops.service.UserAuthenticationService.AuthenticatedUser;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.blankOrNullString;
import static org.hamcrest.Matchers.not;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = {AuthController.class, ActionController.class})
@Import({
        SecurityConfig.class,
        JwtAuthenticationFilter.class,
        JwtTokenProvider.class,
        ServiceJwtAuthenticationFilter.class
})
@TestPropertySource(properties = {
        "jwt.secret=TEST_ONLY_CHANGE_ME_LOCAL_JWT_SECRET_32_CHARS",
        "service-auth.jwt.secret=TEST_ONLY_CHANGE_ME_SERVICE_JWT_SECRET_32_CHARS",
        "app.cors.allowed-origins=http://localhost:3000"
})
class SecurityConfigTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @MockBean
    private ActionPlanService actionPlanService;

    @MockBean
    private AuditService auditService;

    @MockBean
    private UserAuthenticationService authenticationService;

    @BeforeEach
    void configureDatabaseUsers() {
        when(authenticationService.authenticate(anyString(), anyString())).thenAnswer(invocation -> {
            String username = invocation.getArgument(0);
            String password = invocation.getArgument(1);
            if ("admin".equals(username) && "admin123".equals(password)) {
                return Optional.of(user("admin", "ROLE_ADMIN", "ROLE_OPERATOR"));
            }
            if ("operator".equals(username) && "operator123".equals(password)) {
                return Optional.of(user("operator", "ROLE_OPERATOR"));
            }
            if ("viewer".equals(username) && "viewer123".equals(password)) {
                return Optional.of(user("viewer", "ROLE_VIEWER"));
            }
            return Optional.empty();
        });
        when(authenticationService.findEnabledByUsername(anyString())).thenAnswer(invocation -> {
            String username = invocation.getArgument(0);
            return switch (username) {
                case "admin" -> Optional.of(user("admin", "ROLE_ADMIN", "ROLE_OPERATOR"));
                case "operator" -> Optional.of(user("operator", "ROLE_OPERATOR"));
                case "viewer" -> Optional.of(user("viewer", "ROLE_VIEWER"));
                default -> Optional.empty();
            };
        });
    }

    @Test
    void unauthenticatedProtectedApiIsRejected() throws Exception {
        int status = mockMvc.perform(get("/api/actions/pending"))
                .andReturn()
                .getResponse()
                .getStatus();

        assertThat(status).isIn(401, 403);
    }

    @Test
    void loginReturnsJwt() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"viewer","password":"viewer123"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token", not(blankOrNullString())))
                .andExpect(jsonPath("$.token_type").value("Bearer"));
    }

    @Test
    void invalidDatabaseCredentialsAreRejectedWithoutToken() throws Exception {
        mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"viewer","password":"wrong-password"}
                                """))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Invalid username or password"))
                .andExpect(jsonPath("$.access_token").doesNotExist());
    }

    @Test
    void accessAndRefreshTokensAreNotInterchangeable() throws Exception {
        Map<String, Object> login = loginPayload("viewer", "viewer123");
        String accessToken = (String) login.get("access_token");
        String refreshToken = (String) login.get("refresh_token");

        mockMvc.perform(post("/api/auth/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("refreshToken", accessToken))))
                .andExpect(status().isUnauthorized());

        int protectedStatus = mockMvc.perform(get("/api/actions/pending")
                        .header(HttpHeaders.AUTHORIZATION, bearer(refreshToken)))
                .andReturn()
                .getResponse()
                .getStatus();
        assertThat(protectedStatus).isIn(401, 403);

        mockMvc.perform(post("/api/auth/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("refreshToken", refreshToken))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.access_token", not(blankOrNullString())));
    }

    @Test
    void disabledDatabaseUserCannotRefreshAnExistingToken() throws Exception {
        Map<String, Object> login = loginPayload("viewer", "viewer123");
        String refreshToken = (String) login.get("refresh_token");
        when(authenticationService.findEnabledByUsername("viewer")).thenReturn(Optional.empty());

        mockMvc.perform(post("/api/auth/refresh")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of("refreshToken", refreshToken))))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.message").value("Invalid or expired refresh token"));
    }

    @Test
    void viewerCannotApproveOrRejectActions() throws Exception {
        String viewerToken = login("viewer", "viewer123");

        mockMvc.perform(post("/api/actions/plan-1/approve")
                        .header(HttpHeaders.AUTHORIZATION, bearer(viewerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"approvedBy":"admin","notes":"attempt"}
                                """))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/actions/plan-1/reject")
                        .header(HttpHeaders.AUTHORIZATION, bearer(viewerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"rejectedBy":"admin","reason":"attempt"}
                                """))
                .andExpect(status().isForbidden());
    }

    @Test
    void operatorIdentityComesFromJwtInsteadOfRequestBody() throws Exception {
        String operatorToken = login("operator", "operator123");
        when(actionPlanService.approvePlan(eq("plan-1"), eq("operator"), eq("ok")))
                .thenReturn(actionPlan("plan-1", ActionPlan.PlanStatus.EXECUTED));
        when(actionPlanService.rejectPlan(eq("plan-2"), eq("operator"), eq("not needed")))
                .thenReturn(actionPlan("plan-2", ActionPlan.PlanStatus.REJECTED));

        mockMvc.perform(post("/api/actions/plan-1/approve")
                        .header(HttpHeaders.AUTHORIZATION, bearer(operatorToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"approvedBy":"admin","notes":"ok"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("executed"))
                .andExpect(jsonPath("$.planStatus").value("EXECUTED"));

        mockMvc.perform(post("/api/actions/plan-2/reject")
                        .header(HttpHeaders.AUTHORIZATION, bearer(operatorToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"rejectedBy":"admin","reason":"not needed"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("rejected"))
                .andExpect(jsonPath("$.planStatus").value("REJECTED"));

        verify(actionPlanService).approvePlan("plan-1", "operator", "ok");
        verify(actionPlanService).rejectPlan("plan-2", "operator", "not needed");
    }

    @Test
    void safetyRejectedApprovalIsNotReportedAsSuccess() throws Exception {
        String operatorToken = login("operator", "operator123");
        ActionPlan rejected = actionPlan("plan-safety", ActionPlan.PlanStatus.REJECTED);
        rejected.setRejectionReason("Safety validation failed at logical layer");
        when(actionPlanService.approvePlan(eq("plan-safety"), eq("operator"), any()))
                .thenReturn(rejected);

        mockMvc.perform(post("/api/actions/plan-safety/approve")
                        .header(HttpHeaders.AUTHORIZATION, bearer(operatorToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"notes":"approve if safe"}
                                """))
                .andExpect(status().isUnprocessableEntity())
                .andExpect(jsonPath("$.status").value("rejected"))
                .andExpect(jsonPath("$.planStatus").value("REJECTED"))
                .andExpect(jsonPath("$.reason").value("Safety validation failed at logical layer"));
    }

    @Test
    void executionFailureIsNotReportedAsSuccess() throws Exception {
        String operatorToken = login("operator", "operator123");
        ActionPlan failed = actionPlan("plan-failed", ActionPlan.PlanStatus.FAILED);
        failed.setExecutionError("Kafka unavailable");
        when(actionPlanService.approvePlan(eq("plan-failed"), eq("operator"), any()))
                .thenReturn(failed);

        mockMvc.perform(post("/api/actions/plan-failed/approve")
                        .header(HttpHeaders.AUTHORIZATION, bearer(operatorToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"notes":"approve"}
                                """))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.status").value("failed"))
                .andExpect(jsonPath("$.planStatus").value("FAILED"))
                .andExpect(jsonPath("$.error").value("Kafka unavailable"));
    }

    @Test
    void adminCanAccessProtectedEndpoint() throws Exception {
        String adminToken = login("admin", "admin123");
        when(actionPlanService.getPlanStatistics()).thenReturn(Map.of("pending", 1L));

        mockMvc.perform(get("/api/actions/statistics")
                        .header(HttpHeaders.AUTHORIZATION, bearer(adminToken)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.pending").value(1));
    }

    private String login(String username, String password) throws Exception {
        return (String) loginPayload(username, password).get("access_token");
    }

    private Map<String, Object> loginPayload(String username, String password) throws Exception {
        String response = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","password":"%s"}
                                """.formatted(username, password)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        return objectMapper.readValue(response, new TypeReference<>() {});
    }

    private static String bearer(String token) {
        return "Bearer " + token;
    }

    private static ActionPlan actionPlan(String planId, ActionPlan.PlanStatus status) {
        return ActionPlan.builder()
                .planId(planId)
                .traceId("trace-1")
                .farmId("farm-1")
                .targetAssetId("device-1")
                .actionCategory("irrigation")
                .actionType("turn_on")
                .status(status)
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .generatedAt(Instant.now())
                .build();
    }

    private static AuthenticatedUser user(String username, String... roles) {
        return new AuthenticatedUser(username, List.of(roles));
    }
}
