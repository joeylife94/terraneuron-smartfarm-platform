package com.terraneuron.ops.contracts;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.networknt.schema.JsonSchema;
import com.networknt.schema.JsonSchemaFactory;
import com.networknt.schema.SpecVersion;
import com.networknt.schema.ValidationMessage;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class ContractSchemaExamplesTest {

    private static final Path CONTRACTS_DIRECTORY = Path.of(
            System.getProperty("user.dir"), "..", "..", "docs", "contracts").normalize();

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final JsonSchemaFactory schemaFactory =
            JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V7);

    @Test
    void everyContractSchemaLoadsAndValidatesItsExamples() throws IOException {
        assertThat(CONTRACTS_DIRECTORY).isDirectory();

        List<Path> schemaFiles;
        try (var paths = Files.list(CONTRACTS_DIRECTORY)) {
            schemaFiles = paths
                    .filter(path -> path.getFileName().toString().endsWith(".schema.json"))
                    .sorted()
                    .toList();
        }

        assertThat(schemaFiles).extracting(path -> path.getFileName().toString())
                .contains("command.schema.json", "feedback.schema.json")
                .hasSizeGreaterThanOrEqualTo(4);

        for (Path schemaFile : schemaFiles) {
            JsonNode schemaDocument = objectMapper.readTree(schemaFile.toFile());
            JsonSchema schema = schemaFactory.getSchema(schemaDocument);
            JsonNode examples = schemaDocument.path("examples");

            assertThat(examples.isArray())
                    .as("%s has an examples array", schemaFile.getFileName())
                    .isTrue();
            assertThat(examples).as("%s has at least one example", schemaFile.getFileName())
                    .isNotEmpty();

            for (JsonNode example : examples) {
                Set<ValidationMessage> errors = schema.validate(example);
                assertThat(errors)
                        .as("embedded example in %s is valid", schemaFile.getFileName())
                        .isEmpty();
            }
        }
    }
}
