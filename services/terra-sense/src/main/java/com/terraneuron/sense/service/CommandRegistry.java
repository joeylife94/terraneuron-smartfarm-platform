package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceCommand;

import java.time.Instant;
import java.util.Optional;

/**
 * Durable command correlation and idempotency boundary.
 *
 * A command must obtain a publish lease before MQTT publication. Once MQTT
 * publication succeeds, the command is marked PUBLISHED so Kafka redelivery can
 * replay feedback without repeating the physical command.
 */
public interface CommandRegistry {

    Registration register(DeviceCommand command);

    void markPublished(String commandId);

    Optional<DeviceCommand> findPending(String commandId);

    /**
     * Atomically claim a terminal device acknowledgement.
     *
     * @return true only for the first terminal acknowledgement for the command
     */
    boolean claimCompletion(String commandId, String terminalStatus, String error);

    /** Remove pending publication data after terminal feedback is acknowledged by Kafka. */
    void finishCompletion(String commandId);

    /** Release a completion claim when terminal feedback could not be published. */
    void rollbackCompletion(String commandId);

    /** Release publication state when MQTT publication failed. */
    void releasePending(String commandId);

    long pendingCount();

    enum RegistrationState {
        SHOULD_PUBLISH,
        PUBLISH_IN_PROGRESS,
        PUBLISHED,
        COMPLETED
    }

    record Registration(RegistrationState state) {
        public boolean shouldPublish() {
            return state == RegistrationState.SHOULD_PUBLISH;
        }

        public boolean isPublishInProgress() {
            return state == RegistrationState.PUBLISH_IN_PROGRESS;
        }

        public boolean isPublishedDuplicate() {
            return state == RegistrationState.PUBLISHED;
        }

        public boolean isCompletedDuplicate() {
            return state == RegistrationState.COMPLETED;
        }
    }

    record CommandCompletion(
            DeviceCommand command,
            String terminalStatus,
            String error,
            Instant completedAt) {
    }
}
