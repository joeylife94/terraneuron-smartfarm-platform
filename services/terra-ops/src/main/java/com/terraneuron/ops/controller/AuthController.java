package com.terraneuron.ops.controller;

import com.terraneuron.ops.security.JwtTokenProvider;
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
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.Optional;

/**
 * Authentication Controller
 * Handles JWT token generation and validation.
 */
@Slf4j
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Tag(name = "Authentication", description = "JWT authentication endpoints")
public class AuthController {

    private final JwtTokenProvider tokenProvider;
    private final UserAuthenticationService authenticationService;

    @PostMapping("/login")
    @Operation(summary = "Login and get JWT tokens", 
               description = "Returns access and refresh tokens for valid credentials")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest request) {
        log.info("🔐 Login attempt");

        Optional<AuthenticatedUser> authenticated = authenticationService.authenticate(
                request.getUsername(),
                request.getPassword()
        );
        if (authenticated.isEmpty()) {
            log.warn("❌ Login failed");
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid username or password"
            ));
        }

        AuthenticatedUser user = authenticated.get();
        String accessToken = tokenProvider.generateToken(user.username(), user.rolesClaim());
        String refreshToken = tokenProvider.generateRefreshToken(user.username());

        log.info("✅ Login successful for user: {}", user.username());

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "access_token", accessToken,
                "refresh_token", refreshToken,
                "token_type", "Bearer",
                "expires_in", tokenProvider.getAccessTokenExpirationSeconds(),
                "user", Map.of(
                        "username", user.username(),
                        "roles", user.roles()
                )
        ));
    }

    @PostMapping("/refresh")
    @Operation(summary = "Refresh access token", 
               description = "Returns a new access token using a valid refresh token")
    public ResponseEntity<?> refresh(@Valid @RequestBody RefreshRequest request) {
        String refreshToken = request.getRefreshToken();

        if (!tokenProvider.validateRefreshToken(refreshToken)) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid or expired refresh token"
            ));
        }

        String username = tokenProvider.getUsernameFromToken(refreshToken);
        Optional<AuthenticatedUser> account = authenticationService.findEnabledByUsername(username);

        if (account.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid or expired refresh token"
            ));
        }

        AuthenticatedUser user = account.get();
        String newAccessToken = tokenProvider.generateToken(user.username(), user.rolesClaim());

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "access_token", newAccessToken,
                "token_type", "Bearer",
                "expires_in", tokenProvider.getAccessTokenExpirationSeconds()
        ));
    }

    @GetMapping("/validate")
    @Operation(summary = "Validate JWT token", 
               description = "Checks if a token is valid and returns user info")
    public ResponseEntity<?> validate(@RequestHeader("Authorization") String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Missing or invalid Authorization header"
            ));
        }

        String token = authHeader.substring(7);

        if (!tokenProvider.validateAccessToken(token)) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid or expired token"
            ));
        }

        String username = tokenProvider.getUsernameFromToken(token);
        Optional<AuthenticatedUser> account = authenticationService.findEnabledByUsername(username);
        if (account.isEmpty()) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid or expired token"
            ));
        }

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "valid", true,
                "user", Map.of(
                        "username", account.get().username(),
                        "roles", account.get().roles()
                )
        ));
    }

    // ========== DTOs ==========

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
        private String refreshToken;
    }
}
