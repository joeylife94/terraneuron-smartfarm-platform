package com.terraneuron.ops.controller;

import com.terraneuron.ops.security.JwtTokenProvider;
import com.terraneuron.ops.service.RefreshTokenService;
import com.terraneuron.ops.service.RefreshTokenService.RotationResult;
import com.terraneuron.ops.service.UserAuthenticationService;
import com.terraneuron.ops.service.UserAuthenticationService.AuthenticatedUser;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class AuthControllerRefreshTokenTest {

    private JwtTokenProvider tokenProvider;
    private RefreshTokenService refreshTokenService;
    private AuthController controller;

    @BeforeEach
    void setUp() {
        tokenProvider = mock(JwtTokenProvider.class);
        refreshTokenService = mock(RefreshTokenService.class);
        controller = new AuthController(
                tokenProvider,
                mock(UserAuthenticationService.class),
                refreshTokenService);
    }

    @Test
    void refreshReturnsBothNewAccessAndRefreshTokens() {
        AuthController.RefreshRequest request = new AuthController.RefreshRequest();
        request.setRefreshToken("old-refresh");
        AuthenticatedUser user = new AuthenticatedUser("admin", List.of("ROLE_ADMIN"));
        when(refreshTokenService.rotate("old-refresh")).thenReturn(Optional.of(
                new RotationResult(user, "new-refresh", Instant.now().plusSeconds(600))));
        when(tokenProvider.generateToken("admin", "ROLE_ADMIN")).thenReturn("new-access");
        when(tokenProvider.getAccessTokenExpirationSeconds()).thenReturn(60L);
        when(tokenProvider.getRefreshTokenExpirationSeconds()).thenReturn(600L);

        ResponseEntity<?> response = controller.refresh(request);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(response.getBody()).isInstanceOf(Map.class);
        Map<?, ?> body = (Map<?, ?>) response.getBody();
        assertThat(body.get("access_token")).isEqualTo("new-access");
        assertThat(body.get("refresh_token")).isEqualTo("new-refresh");
    }

    @Test
    void rejectedRotationReturnsUnauthorized() {
        AuthController.RefreshRequest request = new AuthController.RefreshRequest();
        request.setRefreshToken("invalid-refresh");
        when(refreshTokenService.rotate("invalid-refresh")).thenReturn(Optional.empty());

        ResponseEntity<?> response = controller.refresh(request);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    void logoutIsIdempotentAndReturnsNoContent() {
        AuthController.RefreshRequest request = new AuthController.RefreshRequest();
        request.setRefreshToken("refresh-token");

        ResponseEntity<Void> response = controller.logout(request);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.NO_CONTENT);
        verify(refreshTokenService).revoke("refresh-token");
    }
}
