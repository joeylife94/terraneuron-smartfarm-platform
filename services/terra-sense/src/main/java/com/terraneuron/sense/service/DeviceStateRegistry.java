package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceStateRecord;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

/** Shared registry abstraction used by MQTT ingestion, safety APIs, and command dispatch. */
public interface DeviceStateRegistry {

    void save(DeviceStateRecord state);

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