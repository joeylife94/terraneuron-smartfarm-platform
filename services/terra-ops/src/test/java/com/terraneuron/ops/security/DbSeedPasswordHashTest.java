package com.terraneuron.ops.security;

import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.io.IOException;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.springframework.core.io.ClassPathResource;

import static org.assertj.core.api.Assertions.assertThat;

class DbSeedPasswordHashTest {

    private static final Pattern SEED_USER = Pattern.compile(
            "\\('(admin|operator|viewer)', '(\\$2[aby]\\$[^']+)'"
    );

    @Test
    void composeSeedContainsWorkingCostTwelveBcryptHashes() throws IOException {
        String sql = new ClassPathResource("db/local/R__compose_seed.sql").getContentAsString(java.nio.charset.StandardCharsets.UTF_8);
        Matcher matcher = SEED_USER.matcher(sql);
        Map<String, String> passwords = Map.of(
                "admin", "admin123",
                "operator", "operator123",
                "viewer", "viewer123"
        );
        BCryptPasswordEncoder encoder = new BCryptPasswordEncoder();
        int matchedUsers = 0;

        while (matcher.find()) {
            String username = matcher.group(1);
            String hash = matcher.group(2);
            assertThat(hash).startsWith("$2b$12$");
            assertThat(encoder.matches(passwords.get(username), hash)).isTrue();
            matchedUsers++;
        }

        assertThat(matchedUsers).isEqualTo(passwords.size());
    }
}
