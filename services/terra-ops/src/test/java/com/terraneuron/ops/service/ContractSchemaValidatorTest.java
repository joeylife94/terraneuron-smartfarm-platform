package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.io.ClassPathResource;

import java.io.InputStream;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThatCode;

class ContractSchemaValidatorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ContractSchemaValidator validator = new ContractSchemaValidator(objectMapper);

    @ParameterizedTest
    @ValueSource(strings = {
            ContractSchemaValidator.ACTION_PLAN_SCHEMA,
            ContractSchemaValidator.PROCESSED_INSIGHT_SCHEMA,
            ContractSchemaValidator.FEEDBACK_SCHEMA
    })
    void packagedContractSchemaLoadsAndValidatesItsExample(String schemaName) throws Exception {
        ClassPathResource resource = new ClassPathResource("contracts/" + schemaName);
        Map<String, Object> example;
        try (InputStream inputStream = resource.getInputStream()) {
            JsonNode schemaDocument = objectMapper.readTree(inputStream);
            example = objectMapper.convertValue(
                    schemaDocument.path("examples").get(0),
                    new TypeReference<Map<String, Object>>() {});
        }

        assertThatCode(() -> validator.validate(schemaName, example))
                .doesNotThrowAnyException();
    }
}
