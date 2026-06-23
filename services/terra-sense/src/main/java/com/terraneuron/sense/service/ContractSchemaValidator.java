package com.terraneuron.sense.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

/** Validates runtime events against the canonical contract schemas on the classpath. */
@Component
@RequiredArgsConstructor
public class ContractSchemaValidator {

    public static final String COMMAND_SCHEMA = "command.schema.json";

    private static final String RESOURCE_DIRECTORY = "contracts/";

    private final ObjectMapper objectMapper;
    private final JsonSchemaFactory schemaFactory =
            JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V7);
    private final Map<String, JsonSchema> schemas = new ConcurrentHashMap<>();

    public void validate(String schemaName, Map<String, Object> event) {
        if (event == null) {
            throw new IllegalArgumentException("Cannot validate a null event against " + schemaName);
        }

        JsonNode eventNode = objectMapper.valueToTree(event);
        Set<ValidationMessage> errors = schema(schemaName).validate(eventNode);
        if (!errors.isEmpty()) {
            String details = errors.stream()
                    .map(ValidationMessage::getMessage)
                    .sorted()
                    .collect(Collectors.joining("; "));
            throw new IllegalArgumentException(
                    "Event does not match contract " + schemaName + ": " + details);
        }
    }

    private JsonSchema schema(String schemaName) {
        return schemas.computeIfAbsent(schemaName, this::loadSchema);
    }

    private JsonSchema loadSchema(String schemaName) {
        ClassPathResource resource = new ClassPathResource(RESOURCE_DIRECTORY + schemaName);
        try (InputStream inputStream = resource.getInputStream()) {
            return schemaFactory.getSchema(objectMapper.readTree(inputStream));
        } catch (IOException e) {
            throw new IllegalStateException(
                    "Unable to load contract schema from classpath: " + resource.getPath(), e);
        }
    }
}
