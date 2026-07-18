package com.terraneuron.ops.service.safety;

import com.terraneuron.ops.entity.ActionPlan;

/** Fail-closed boundary used by SafetyValidator layer 4. */
public interface DeviceSafetyClient {

    DeviceSafetyResult evaluate(ActionPlan plan);

    record DeviceSafetyResult(boolean allowed, String reasonCode) {
        public static DeviceSafetyResult allow() {
            return new DeviceSafetyResult(true, "ALLOWED");
        }

        public static DeviceSafetyResult blocked(String reasonCode) {
            return new DeviceSafetyResult(false,
                    reasonCode == null || reasonCode.isBlank()
                            ? "SENSE_MALFORMED_RESPONSE"
                            : reasonCode);
        }
    }
}
