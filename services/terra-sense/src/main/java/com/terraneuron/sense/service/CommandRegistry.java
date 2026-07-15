package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceCommand;

import java.time.Instant;
import java.util.Optional;

/**
 * Durable command correlation and idempotency boundary.
 *
 * A command must be registered before MQTT publication. The registration survives
 * Terra-Sense restarts and prevents Kafka redelivery from publishing the same
 * physical command more than once.
 */
public interface CommandRegistry {

    Registration register(DeviceCommand command);

    Optional<DeviceCommand> findPending(String commandId);

    /**
     * Atomically claim a terminal device acknowledgement.
     *
     * @return true only for the first terminal acknowledgement for the command
     */
    boolean claimCompletion(String commandId, String terminalStatus, String error);

    /** Remove the pending command after terminal feedback is acknowledged by Kafka. */
    void finishCompletion(String commandId);

    /** Release a completion claim when terminal feedback could not be published. */
    void rollbackCompletion(String commandId);

    /** Release a newly registered command when MQTT publication failed. */
    void releasePending(String commandId);

    long pendingCount();

    enum RegistrationState {
        NEW,
        PENDING,
        COMPLETED
    }

    record Registration(RegistrationState state) {
        public boolean isNew() {
            return state == RegistrationState.NEW;
        }

        public boolean isPendingDuplicate() {
            return state == RegistrationState.PENDING;
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
