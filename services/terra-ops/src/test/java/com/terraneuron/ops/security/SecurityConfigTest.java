package com.terraneuron.ops.security;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.terraneuron.ops.controller.ActionController;
import com.terraneuron.ops.controller.AuthController;
import com.terraneuron.ops.entity.ActionPlan;
import com.terraneuron.ops.service.ActionPlanService;
import com.terraneuron.ops.service.AuditService;
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
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.blankOrNullString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(controllers = {AuthController.class, ActionController.class})
@Import({SecurityConfig.class, JwtAuthenticationFilter.class, JwtTokenProvider.class})
@TestPropertySource(properties = {
        "jwt.secret=TEST_ONLY_CHANGE_ME_LOCAL_JWT_SECRET_32_CHARS",
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
    void viewerCannotApproveOrRejectActions() throws Exception {
        String viewerToken = login("viewer", "viewer123");

        mockMvc.perform(post("/api/actions/plan-1/approve")
                        .header(HttpHeaders.AUTHORIZATION, bearer(viewerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"approvedBy":"viewer","notes":"attempt"}
                                """))
                .andExpect(status().isForbidden());

        mockMvc.perform(post("/api/actions/plan-1/reject")
                        .header(HttpHeaders.AUTHORIZATION, bearer(viewerToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"rejectedBy":"viewer","reason":"attempt"}
                                """))
                .andExpect(status().isForbidden());
    }

    @Test
    void operatorCanApproveAndRejectActions() throws Exception {
        String operatorToken = login("operator", "operator123");
        when(actionPlanService.approvePlan(eq("plan-1"), anyString(), any()))
                .thenReturn(actionPlan("plan-1"));
        when(actionPlanService.rejectPlan(eq("plan-1"), anyString(), anyString()))
                .thenReturn(actionPlan("plan-1"));

        mockMvc.perform(post("/api/actions/plan-1/approve")
                        .header(HttpHeaders.AUTHORIZATION, bearer(operatorToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"approvedBy":"operator","notes":"ok"}
                                """))
                .andExpect(status().isOk());

        mockMvc.perform(post("/api/actions/plan-1/reject")
                        .header(HttpHeaders.AUTHORIZATION, bearer(operatorToken))
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"rejectedBy":"operator","reason":"not needed"}
                                """))
                .andExpect(status().isOk());
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
        String response = mockMvc.perform(post("/api/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"username":"%s","password":"%s"}
                                """.formatted(username, password)))
                .andExpect(status().isOk())
                .andReturn()
                .getResponse()
                .getContentAsString();

        Map<String, Object> body = objectMapper.readValue(response, new TypeReference<>() {});
        return (String) body.get("access_token");
    }

    private static String bearer(String token) {
        return "Bearer " + token;
    }

    private static ActionPlan actionPlan(String planId) {
        return ActionPlan.builder()
                .planId(planId)
                .traceId("trace-1")
                .farmId("farm-1")
                .targetAssetId("device-1")
                .actionCategory("irrigation")
                .actionType("turn_on")
                .status(ActionPlan.PlanStatus.PENDING)
                .priority(ActionPlan.ActionPriority.MEDIUM)
                .generatedAt(Instant.now())
                .build();
    }
}
