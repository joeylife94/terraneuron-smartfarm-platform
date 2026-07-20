package com.terraneuron.sense.service;

/** Signals that the shared registry cannot be trusted; safety callers must fail closed. */
public class DeviceStateRegistryUnavailableException extends RuntimeException {

    public DeviceStateRegistryUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}