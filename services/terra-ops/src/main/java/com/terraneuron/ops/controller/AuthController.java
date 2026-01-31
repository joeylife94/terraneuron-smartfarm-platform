package com.terraneuron.ops.controller;

import com.terraneuron.ops.security.JwtTokenProvider;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

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

    // Hardcoded users for development (replace with database in production)
    private static final Map<String, UserInfo> USERS = Map.of(
            "admin", new UserInfo("admin", "admin123", "ROLE_ADMIN,ROLE_OPERATOR"),
            "operator", new UserInfo("operator", "operator123", "ROLE_OPERATOR"),
            "viewer", new UserInfo("viewer", "viewer123", "ROLE_VIEWER")
    );

    @PostMapping("/login")
    @Operation(summary = "Login and get JWT tokens", 
               description = "Returns access and refresh tokens for valid credentials")
    public ResponseEntity<?> login(@RequestBody LoginRequest request) {
        log.info("🔐 Login attempt for user: {}", request.getUsername());

        UserInfo user = USERS.get(request.getUsername());
        if (user == null || !user.password.equals(request.getPassword())) {
            log.warn("❌ Login failed for user: {}", request.getUsername());
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid username or password"
            ));
        }

        String accessToken = tokenProvider.generateToken(user.username, user.roles);
        String refreshToken = tokenProvider.generateRefreshToken(user.username);

        log.info("✅ Login successful for user: {}", request.getUsername());

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "access_token", accessToken,
                "refresh_token", refreshToken,
                "token_type", "Bearer",
                "expires_in", 86400,
                "user", Map.of(
                        "username", user.username,
                        "roles", user.roles.split(",")
                )
        ));
    }

    @PostMapping("/refresh")
    @Operation(summary = "Refresh access token", 
               description = "Returns a new access token using a valid refresh token")
    public ResponseEntity<?> refresh(@RequestBody RefreshRequest request) {
        String refreshToken = request.getRefreshToken();

        if (!tokenProvider.validateToken(refreshToken)) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid or expired refresh token"
            ));
        }

        String username = tokenProvider.getUsernameFromToken(refreshToken);
        UserInfo user = USERS.get(username);

        if (user == null) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "User not found"
            ));
        }

        String newAccessToken = tokenProvider.generateToken(user.username, user.roles);

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "access_token", newAccessToken,
                "token_type", "Bearer",
                "expires_in", 86400
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

        if (!tokenProvider.validateToken(token)) {
            return ResponseEntity.status(401).body(Map.of(
                    "status", "error",
                    "message", "Invalid or expired token"
            ));
        }

        String username = tokenProvider.getUsernameFromToken(token);
        String roles = tokenProvider.getRolesFromToken(token);

        return ResponseEntity.ok(Map.of(
                "status", "success",
                "valid", true,
                "user", Map.of(
                        "username", username,
                        "roles", roles.split(",")
                )
        ));
    }

    // ========== DTOs ==========

    @Data
    public static class LoginRequest {
        private String username;
        private String password;
    }

    @Data
    public static class RefreshRequest {
        private String refreshToken;
    }

    private static class UserInfo {
        String username;
        String password;
        String roles;

        UserInfo(String username, String password, String roles) {
            this.username = username;
            this.password = password;
            this.roles = roles;
        }
    }
}
