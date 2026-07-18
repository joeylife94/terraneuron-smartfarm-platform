package com.terraneuron.sense.controller;

import com.terraneuron.sense.model.DeviceSafetyDecision;
import com.terraneuron.sense.model.DeviceSafetyRequest;
import com.terraneuron.sense.service.DeviceSafetyPolicy;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** Narrow internal API consumed only by Terra-Ops service credentials. */
@RestController
@RequestMapping("/internal/device-safety")
@RequiredArgsConstructor
public class InternalDeviceSafetyController {

    private final DeviceSafetyPolicy deviceSafetyPolicy;

    @PostMapping("/evaluate")
    public ResponseEntity<DeviceSafetyDecision> evaluate(@RequestBody DeviceSafetyRequest request) {
        return ResponseEntity.ok(deviceSafetyPolicy.evaluate(request));
    }
}