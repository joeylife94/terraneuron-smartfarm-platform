package com.terraneuron.ops.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.core.io.ClassPathResource;

import java.io.InputStream;
import java.util.Map;
import java.util.stream.Stream;

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
        Map<String, Object> example = loadExample(schemaName);

        assertThatCode(() -> validator.validate(schemaName, example))
                .doesNotThrowAnyException();
    }

    @ParameterizedTest
    @MethodSource("advertisedAdjustParameters")
    void actionPlanSchemaAcceptsAdvertisedDeviceAdjustParameters(
            String parameterName,
            Object parameterValue) throws Exception {
        Map<String, Object> event = loadExample(ContractSchemaValidator.ACTION_PLAN_SCHEMA);
        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) event.get("data");
        data.put("action_type", "adjust");
        data.put("parameters", Map.of(parameterName, parameterValue));

        assertThatCode(() -> validator.validate(ContractSchemaValidator.ACTION_PLAN_SCHEMA, event))
                .doesNotThrowAnyException();
    }

    private Map<String, Object> loadExample(String schemaName) throws Exception {
        ClassPathResource resource = new ClassPathResource("contracts/" + schemaName);
        try (InputStream inputStream = resource.getInputStream()) {
            JsonNode schemaDocument = objectMapper.readTree(inputStream);
            return objectMapper.convertValue(
                    schemaDocument.path("examples").get(0),
                    new TypeReference<Map<String, Object>>() {});
        }
    }

    private static Stream<Arguments> advertisedAdjustParameters() {
        return Stream.of(
                Arguments.of("power_percentage", 50),
                Arguments.of("position_percentage", 50),
                Arguments.of("flow_rate", 1.5),
                Arguments.of("target_humidity", 65.0),
                Arguments.of("target_temperature", 24.5),
                Arguments.of("brightness_percentage", 80));
    }
}
