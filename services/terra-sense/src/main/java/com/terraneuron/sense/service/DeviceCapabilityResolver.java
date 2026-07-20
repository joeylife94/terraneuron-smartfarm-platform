package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceStateRecord;

import java.util.Optional;
import java.util.Set;

/**
 * Extension point for manufacturer/model-specific capability adapters.
 * Higher-priority resolvers may be added without changing the core safety policy.
 */
public interface DeviceCapabilityResolver {

    Optional<DeviceCapabilities> resolve(DeviceStateRecord state);

    record DeviceCapabilities(
            Set<String> actionCategories,
            Set<String> actionTypes,
            Set<String> adjustParameterAnyOf
    ) {
        public DeviceCapabilities {
            actionCategories = Set.copyOf(actionCategories);
            actionTypes = Set.copyOf(actionTypes);
            adjustParameterAnyOf = Set.copyOf(adjustParameterAnyOf);
        }
    }
}