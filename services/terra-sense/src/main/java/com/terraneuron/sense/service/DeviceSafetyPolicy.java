package com.terraneuron.sense.service;

import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyRequest;

public interface DeviceSafetyPolicy {

    DeviceSafetyDecision evaluate(DeviceSafetyRequest request);
}