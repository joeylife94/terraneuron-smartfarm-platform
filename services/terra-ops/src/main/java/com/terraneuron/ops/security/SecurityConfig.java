package com.terraneuron.ops.security;

import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

/**
 * Security Configuration
 * Configures JWT-based authentication and authorization.
 */
@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthenticationFilter jwtAuthenticationFilter;
    private final ServiceJwtAuthenticationFilter serviceJwtAuthenticationFilter;

    @Value("${app.cors.allowed-origins:http://localhost:3000,http://localhost:3001}")
    private String allowedOrigins;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
            // Stateless REST API: each request uses a JWT bearer token, so CSRF protection is not needed.
            .csrf(AbstractHttpConfigurer::disable)
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                // Public endpoints (no authentication required)
                .requestMatchers("/api/auth/**").permitAll()
                .requestMatchers("/actuator/health").permitAll()
                .requestMatchers("/swagger-ui/**", "/v3/api-docs", "/v3/api-docs/**").permitAll()

                // Administrative and management endpoints
                .requestMatchers("/actuator/**").hasRole("ADMIN")

                // Operational action mutations
                .requestMatchers(HttpMethod.POST, "/api/actions/*/approve", "/api/actions/*/reject")
                    .hasAnyRole("ADMIN", "OPERATOR")

                // Crop and farm operational mutations
                .requestMatchers(HttpMethod.POST, "/api/farms/*/crops").hasAnyRole("ADMIN", "OPERATOR")
                .requestMatchers(HttpMethod.PUT, "/api/farms/*/crops/*/advance-stage").hasAnyRole("ADMIN", "OPERATOR")

                // Terra-Cortex receives one narrowly scoped read permission. The service filter only
                // authenticates this exact route, so its token cannot satisfy other authenticated routes.
                .requestMatchers(HttpMethod.GET, "/api/farms/*/optimal-conditions")
                    .hasAnyAuthority("ROLE_ADMIN", "ROLE_OPERATOR", "ROLE_VIEWER", "SCOPE_crop:read")

                // Read-only application APIs
                .requestMatchers(HttpMethod.GET, "/api/actions/**").hasAnyRole("ADMIN", "OPERATOR", "VIEWER")
                .requestMatchers(HttpMethod.GET, "/api/crops/**").hasAnyRole("ADMIN", "OPERATOR", "VIEWER")
                .requestMatchers(HttpMethod.GET, "/api/farms/*/crops").hasAnyRole("ADMIN", "OPERATOR", "VIEWER")
                .requestMatchers(HttpMethod.GET, "/api/v1/**").hasAnyRole("ADMIN", "OPERATOR", "VIEWER")

                // Unknown routes are authenticated, but not assigned an invented role rule.
                .anyRequest().authenticated()
            )
            // Custom filters cannot be used as relative order anchors in Spring Security. Both are
            // placed before the framework authentication filter; either order is safe because the user
            // filter never clears an authentication established by the scoped service filter.
            .addFilterBefore(serviceJwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
            .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(parseAllowedOrigins());
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(Arrays.asList("Authorization", "Content-Type", "X-Trace-ID", "Accept"));
        configuration.setExposedHeaders(List.of("X-Trace-ID"));
        configuration.setAllowCredentials(false);
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    private List<String> parseAllowedOrigins() {
        List<String> origins = Arrays.stream(allowedOrigins.split(","))
                .map(String::trim)
                .filter(origin -> !origin.isEmpty())
                .toList();

        if (origins.isEmpty() || origins.contains("*")) {
            throw new IllegalStateException("CORS allowed origins must be explicit; wildcard '*' is not allowed.");
        }

        return origins;
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
