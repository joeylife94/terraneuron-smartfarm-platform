package com.terraneuron.ops.service;

import com.terraneuron.ops.entity.UserAccount;
import com.terraneuron.ops.repository.UserAccountRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.startsWith;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class UserAuthenticationServiceTest {

    @Mock
    private UserAccountRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @InjectMocks
    private UserAuthenticationService authenticationService;

    @Test
    void validBcryptCredentialsLoadRolesAndRecordLastLogin() {
        UserAccount account = account(true, "ROLE_ADMIN, ROLE_OPERATOR");
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(account));
        when(passwordEncoder.matches("admin123", account.getPasswordHash())).thenReturn(true);

        Optional<UserAuthenticationService.AuthenticatedUser> result =
                authenticationService.authenticate(" ADMIN ", "admin123");

        assertThat(result).isPresent();
        assertThat(result.get().username()).isEqualTo("admin");
        assertThat(result.get().roles()).containsExactly("ROLE_ADMIN", "ROLE_OPERATOR");
        assertThat(result.get().rolesClaim()).isEqualTo("ROLE_ADMIN,ROLE_OPERATOR");
        assertThat(account.getLastLogin()).isNotNull();
        verify(userRepository).save(account);
    }

    @Test
    void wrongPasswordAndDisabledAccountFailClosed() {
        UserAccount wrongPassword = account(true, "ROLE_VIEWER");
        when(userRepository.findByUsername("admin"))
                .thenReturn(Optional.of(wrongPassword));
        when(passwordEncoder.matches("wrong", wrongPassword.getPasswordHash())).thenReturn(false);

        assertThat(authenticationService.authenticate("admin", "wrong")).isEmpty();
        verify(userRepository, never()).save(wrongPassword);

        UserAccount disabled = account(false, "ROLE_VIEWER");
        when(userRepository.findByUsername("viewer")).thenReturn(Optional.of(disabled));
        when(passwordEncoder.matches("viewer123", disabled.getPasswordHash())).thenReturn(true);

        assertThat(authenticationService.authenticate("viewer", "viewer123")).isEmpty();
        verify(userRepository, never()).save(disabled);
    }

    @Test
    void unknownUsernameStillPerformsDummyBcryptComparison() {
        when(userRepository.findByUsername("missing")).thenReturn(Optional.empty());

        assertThat(authenticationService.authenticate("missing", "secret")).isEmpty();

        verify(passwordEncoder).matches("secret", startsWith("$2b$12$"));
    }

    @Test
    void unknownOrEmptyRoleFailsClosed() {
        UserAccount unknownRole = account(true, "ROLE_OWNER");
        when(userRepository.findByUsername("admin")).thenReturn(Optional.of(unknownRole));
        when(passwordEncoder.matches("admin123", unknownRole.getPasswordHash())).thenReturn(true);

        assertThat(authenticationService.authenticate("admin", "admin123")).isEmpty();
        assertThat(authenticationService.findEnabledByUsername("admin")).isEmpty();
        verify(userRepository, never()).save(unknownRole);
    }

    @Test
    void refreshLookupReloadsCurrentEnabledRoles() {
        UserAccount account = account(true, "ROLE_VIEWER");
        when(userRepository.findByUsername("viewer")).thenReturn(Optional.of(account));

        Optional<UserAuthenticationService.AuthenticatedUser> result =
                authenticationService.findEnabledByUsername("VIEWER");

        assertThat(result).isPresent();
        assertThat(result.get().roles()).containsExactly("ROLE_VIEWER");
    }

    private static UserAccount account(boolean enabled, String roles) {
        return UserAccount.builder()
                .username(roles.contains("ADMIN") ? "admin" : "viewer")
                .passwordHash("$2b$12$stored-hash")
                .roles(roles)
                .enabled(enabled)
                .build();
    }
}
