package com.terraneuron.sense.model;

/** Stable, non-sensitive reason codes used by APIs, metrics, feedback, and audit logs. */
public enum DeviceSafetyReason {
    ALLOWED,
    REGISTRY_UNAVAILABLE,
    STATE_MISSING,
    IDENTITY_MISMATCH,
    STATE_STALE,
    REPORTED_STATE_STALE,
    REPORTED_TIME_INVALID,
    STATE_OFFLINE,
    STATE_ERROR,
    STATE_UNKNOWN,
    MAINTENANCE_MODE,
    UNSUPPORTED_DEVICE_TYPE,
    ACTION_CATEGORY_MISMATCH,
    ACTION_UNSUPPORTED,
    ADJUST_PARAMETERS_MISSING
}