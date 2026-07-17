package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.UserAccount;
import com.terraneuron.ops.repository.UserAccountRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.Instant;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

/** Authenticates Terra-Ops users against BCrypt hashes stored in MySQL. */
@Slf4j
@Service
@RequiredArgsConstructor
public class UserAuthenticationService {

    private static final String DUMMY_BCRYPT_HASH =
            "$2b$12$VEM9UEYzvq2FvUZeU7o9h.E5HuNxFRnz.arT1lhOtdi6kMFt9ETki";
    private static final Set<String> ALLOWED_ROLES = Set.of(
            "ROLE_ADMIN",
            "ROLE_OPERATOR",
            "ROLE_VIEWER"
    );

    private final UserAccountRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    /**
     * Verifies credentials and records the successful login time atomically.
     * Unknown users still execute one BCrypt comparison to reduce username
     * enumeration through response-time differences.
     */
    @Transactional
    public Optional<AuthenticatedUser> authenticate(String username, String rawPassword) {
        String normalizedUsername = normalizeUsername(username);
        if (!StringUtils.hasText(normalizedUsername) || rawPassword == null) {
            performDummyPasswordCheck(rawPassword);
            return Optional.empty();
        }

        Optional<UserAccount> candidate = userRepository.findByUsername(normalizedUsername);
        if (candidate.isEmpty()) {
            performDummyPasswordCheck(rawPassword);
            return Optional.empty();
        }

        UserAccount account = candidate.get();
        boolean passwordMatches;
        try {
            passwordMatches = passwordEncoder.matches(rawPassword, account.getPasswordHash());
        } catch (IllegalArgumentException exception) {
            log.error("Authentication rejected because an account password hash is invalid");
            return Optional.empty();
        }

        if (!passwordMatches || !account.isEnabled()) {
            return Optional.empty();
        }

        Optional<List<String>> roles = validatedRoles(account.getRoles());
        if (roles.isEmpty()) {
            log.error("Authentication rejected because an account has invalid roles");
            return Optional.empty();
        }

        account.setLastLogin(Instant.now());
        userRepository.save(account);
        return Optional.of(new AuthenticatedUser(account.getUsername(), roles.get()));
    }

    /** Reloads enabled account state and roles before an access token is refreshed. */
    @Transactional(readOnly = true)
    public Optional<AuthenticatedUser> findEnabledByUsername(String username) {
        String normalizedUsername = normalizeUsername(username);
        if (!StringUtils.hasText(normalizedUsername)) {
            return Optional.empty();
        }

        return userRepository.findByUsername(normalizedUsername)
                .filter(UserAccount::isEnabled)
                .flatMap(account -> validatedRoles(account.getRoles())
                        .map(roles -> new AuthenticatedUser(account.getUsername(), roles)));
    }

    private void performDummyPasswordCheck(String rawPassword) {
        passwordEncoder.matches(rawPassword == null ? "" : rawPassword, DUMMY_BCRYPT_HASH);
    }

    private static String normalizeUsername(String username) {
        return username == null ? null : username.trim().toLowerCase(Locale.ROOT);
    }

    private static Optional<List<String>> validatedRoles(String storedRoles) {
        if (!StringUtils.hasText(storedRoles)) {
            return Optional.empty();
        }

        LinkedHashSet<String> roles = new LinkedHashSet<>();
        Arrays.stream(storedRoles.split(","))
                .map(String::trim)
                .filter(StringUtils::hasText)
                .forEach(roles::add);

        if (roles.isEmpty() || !ALLOWED_ROLES.containsAll(roles)) {
            return Optional.empty();
        }
        return Optional.of(List.copyOf(roles));
    }

    public record AuthenticatedUser(String username, List<String> roles) {

        public AuthenticatedUser {
            roles = List.copyOf(roles);
        }

        public String rolesClaim() {
            return String.join(",", roles);
        }
    }
}
