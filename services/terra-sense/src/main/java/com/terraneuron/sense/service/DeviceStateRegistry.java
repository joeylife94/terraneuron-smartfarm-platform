package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceStateRecord;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

/** Shared registry abstraction used by MQTT ingestion, safety APIs, and command dispatch. */
public interface DeviceStateRegistry {

    void save(DeviceStateRecord state);

    /**
     * Make an existing state record non-authoritative after an ingestion failure.
     * Implementations should block local reads immediately and remove shared state
     * where possible so another replica cannot authorize from the superseded record.
     */
    default void invalidate(String farmId, String assetId) {
        // Optional for non-production/fake registries. The Redis implementation
        // provides the fail-closed shared invalidation semantics.
    }

    Optional<DeviceStateRecord> find(String farmId, String assetId);

    Map<String, DeviceStateRecord> findAll();

    RegistryStatus status();

    record RegistryStatus(
            String backend,
            boolean available,
            Instant lastSuccessfulReadAt,
            long trackedDevices
    ) { }
}
