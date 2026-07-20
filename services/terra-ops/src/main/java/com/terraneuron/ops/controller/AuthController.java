package com.terraneuron.ops.controller;

import com.terraneuron.ops.security.JwtTokenProvider;
import com.terraneuron.ops.service.RefreshTokenService;
import com.terraneuron.ops.service.RefreshTokenService.IssuedRefreshToken;
import com.terraneuron.ops.service.RefreshTokenService.RotationResult;
import com.terraneuron.ops.service.UserAuthenticationService;
import com.terraneuron.ops.service.UserAuthenticationService.AuthenticatedUser;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.Optional;

/** Authentication endpoints for interactive Terra-Ops users. */
@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Tag(name = "Authentication", description = "JWT authentication endpoints")
public class AuthController {

    private final JwtTokenProvider tokenProvider;
    private final UserAuthenticationService authenticationService;
    private final RefreshTokenService refreshTokenService;

    @PostMapping("/login")
    @Operation(
            summary = "Login and get JWT tokens",
            description = "Returns an access token and a persisted, single-use refresh token")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest request) {
        log.info("Login attempt");

        Optional<AuthenticatedUser> authenticated = authenticationService.authenticate(
                request.getUsername(),
                request.getPassword());
        if (authenticated.isEmpty()) {
            log.warn("Login failed");
            return unauthorized("Invalid username or password");
        }

        AuthenticatedUser user = authenticated.get();
        String accessToken = tokenProvider.generateToken(user.username(), user.rolesClaim());
        IssuedRefreshToken refreshToken = refreshTokenService.issue(user.username());

        log.info("Login successful for user: {}", user.username());
        return ResponseEntity.ok(Map.of(
                "status", "success",
                "access_token", accessToken,
                "refresh_token", refreshToken.token(),
                "token_type", "Bearer",
                "expires_in", tokenProvider.getAccessTokenExpirationSeconds(),
                "refresh_expires_in", tokenProvider.getRefreshTokenExpirationSeconds(),
                "user", Map.of(
                        "username", user.username(),
                        "roles", user.roles())
        ));
    }

    @PostMapping("/refresh")
    @Operation(
            summary = "Rotate refresh token",
            description = "Consumes one active refresh token and returns new access and refresh tokens")
    public ResponseEntity<?> refresh(@Valid @RequestBody RefreshRequest request) {
        Optional<RotationResult> rotated = refreshTokenService.rotate(request.getRefreshToken());
        if (rotated.isEmpty()) {
            return unauthorized("Invalid or expired refresh token");
        }

        RotationResult result = rotated.get();
        AuthenticatedUser user = result.user();
        String accessToken = tokenProvider.generateToken(user.username(), user.rolesClaim());

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "access_token", accessToken,
                "refresh_token", result.refreshToken(),
                "token_type", "Bearer",
                "expires_in", tokenProvider.getAccessTokenExpirationSeconds(),
                "refresh_expires_in", tokenProvider.getRefreshTokenExpirationSeconds()
        ));
    }

    @PostMapping("/logout")
    @Operation(
            summary = "Revoke one refresh token",
            description = "Idempotently revokes the presented refresh token without exposing token state")
    public ResponseEntity<Void> logout(@Valid @RequestBody RefreshRequest request) {
        refreshTokenService.revoke(request.getRefreshToken());
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/validate")
    @Operation(
            summary = "Validate JWT token",
            description = "Checks an access token and reloads current account state and roles")
    public ResponseEntity<?> validate(@RequestHeader("Authorization") String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return unauthorized("Missing or invalid Authorization header");
        }

        String token = authHeader.substring(7);
        if (!tokenProvider.validateAccessToken(token)) {
            return unauthorized("Invalid or expired token");
        }

        String username = tokenProvider.getUsernameFromToken(token);
        Optional<AuthenticatedUser> account = authenticationService.findEnabledByUsername(username);
        if (account.isEmpty()) {
            return unauthorized("Invalid or expired token");
        }

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "valid", true,
                "user", Map.of(
                        "username", account.get().username(),
                        "roles", account.get().roles())
        ));
    }

    private ResponseEntity<?> unauthorized(String message) {
        return ResponseEntity.status(401).body(Map.of(
                "status", "error",
                "message", message
        ));
    }

    @Data
    public static class LoginRequest {
        @NotBlank
        @Size(max = 50)
        private String username;

        @NotBlank
        @Size(max = 200)
        private String password;
    }

    @Data
    public static class RefreshRequest {
        @NotBlank
        @Size(max = 4096)
        private String refreshToken;
    }
}
