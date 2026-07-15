package com.terraneuron.sense.service;

/**
 * Signals that terra-sense could not publish a device command to the MQTT broker.
 *
 * <p>The exception is intentionally unchecked so the Kafka command consumer can convert
 * the failed delivery attempt into a FAILED control-feedback event.</p>
 */
public class MqttPublishException extends RuntimeException {

    public MqttPublishException(String message, Throwable cause) {
        super(message, cause);
    }
}
