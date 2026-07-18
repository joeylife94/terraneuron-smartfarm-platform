# Device Safety Gate

TerraNeuron blocks device commands twice: when an operator approves an action plan in Terra-Ops and immediately before Terra-Sense publishes the command to MQTT.

## Flow

```text
operator approval
  -> Terra-Ops SafetyValidator layer 4
  -> short-lived Ops service JWT
  -> Terra-Sense /internal/device-safety/evaluate
  -> shared Redis device state + capability policy
  -> APPROVED and transactional outbox, or SAFETY_BLOCKED with no outbox
  -> Kafka command
  -> Terra-Sense Redis command claim
  -> identical safety policy recheck
  -> MQTT publish, or terminal FAILED feedback without MQTT publish
```

The approval-time check prevents known-unsafe plans from entering the command outbox. The pre-dispatch check reduces the time-of-check/time-of-use window between approval and physical delivery.

## Shared device state

The registry key is the exact `(farmId, assetId)` pair. Identifiers are encoded into Redis keys and are not used as Prometheus labels.

Each state record contains two timestamps:

- `reportedAt`: supplied by the device.
- `observedAt`: assigned by Terra-Sense when the MQTT status message is accepted.

Both timestamps must be within the configured freshness window. A future `reportedAt` beyond the bounded skew is rejected. MQTT topic identity must match any identity in the payload before the shared registry is updated.

Default configuration:

| Setting | Default | Rationale |
|---|---:|---|
| `DEVICE_STATE_FRESHNESS_SECONDS` | 120 s | Allows several missed status intervals while remaining conservative before the real heartbeat contract is known. |
| `DEVICE_STATE_TTL_SECONDS` | 600 s | Five times the freshness window, so a still-valid record is not removed by TTL before policy evaluation. |
| reported future skew | 10 s | Allows small device clock differences without accepting materially future state. |

The TTL must remain greater than the freshness window. An expired or absent Redis record is `STATE_MISSING`; an existing record older than the freshness window is stale and cannot authorize a command.

Redis read or write failure is fail-closed. This may temporarily block otherwise valid commands.

## Core safety policy

Allowed states are `online`, `running`, and `idle`, subject to every other check. The policy blocks:

- missing or mismatched `(farmId, assetId)` state;
- stale observed state or stale/invalid device-reported time;
- `offline`, `error`, `unknown`, or unrecognized state;
- maintenance mode;
- unknown device type;
- action category incompatible with the explicit device type;
- unsupported action type;
- `adjust` without at least one supported adjustment parameter.

Device type matching is exact after normalization. The implementation never infers device type from an asset identifier substring.

The built-in conservative capability table covers generic `fan`, `vent`, `pump`, `valve`, `humidifier`, `heater`, `cooler`, `dehumidifier`, `led`, and `light` types. `DeviceCapabilityResolver` is the extension point for manufacturer/model-specific adapters. A manufacturer adapter should return an explicit capability set; unknown models remain blocked.

## Approval and retry lifecycle

A human approval is recorded before device safety evaluation. A transient device-state failure changes the plan to `SAFETY_BLOCKED` rather than `REJECTED`:

- approver and approval time are retained;
- no command ID or outbox row is created;
- the plan expiration deadline remains unchanged;
- `POST /api/actions/{planId}/safety/revalidate` is required after state recovery;
- a successful revalidation creates the command and outbox in the same MySQL transaction;
- a second revalidation cannot create another outbox because the plan has already left `SAFETY_BLOCKED` and owns a command ID.

Logical or permission failures remain permanent `REJECTED` outcomes.

## Pre-dispatch behavior

Terra-Sense claims the `commandId` in the existing Redis command registry and then runs the same policy immediately before MQTT publication.

When blocked:

- MQTT is not called;
- Terra-Sense publishes `FAILED` feedback with `DEVICE_SAFETY_BLOCKED:<REASON_CODE>`;
- the original `commandId`, plan, farm, and asset correlation are retained in the feedback contract;
- Terra-Ops moves the command lifecycle to `DELIVERY_FAILED` with result `DEVICE_SAFETY_BLOCKED`;
- the terminal Redis completion marker suppresses Kafka redelivery from producing another MQTT command or duplicate terminal handling.

## Service authentication

Terra-Ops uses a service JWT independent from user JWTs and Cortex-to-Ops credentials:

- subject: `terra-ops`
- issuer: `terraneuron-internal`
- audience: `terra-sense`
- type: `service`
- scope: `device:safety:evaluate`
- default lifetime: 30 seconds
- accepted maximum lifetime: 60 seconds
- default clock skew: 5 seconds

The token is accepted only on `POST /internal/device-safety/evaluate`. Presenting the same service token to another Terra-Sense API returns `403`. User JWTs do not satisfy this internal route.

Use the same random `DEVICE_SAFETY_JWT_SECRET` in Terra-Ops and Terra-Sense. It must be at least 32 bytes and must not reuse the user JWT or Cortex service-auth key.

## Observability

Bounded metrics contain no raw farm, asset, event, command, JWT, or device payload labels:

- `terra_device_safety_evaluations_total{outcome,reason}`
- `terra_device_safety_predispatch_blocks_total{reason}`
- `terra_device_safety_sense_api_requests_total{reason}`
- `terra_device_safety_freshness_seconds`
- `terra_device_state_registry_available`
- `terra_device_state_registry_last_success_epoch_seconds`
- `terra_device_state_registry_ttl_seconds`

The existing Terra-Sense stats endpoint exposes only aggregate registry backend, availability, tracked-device count, and last successful read time.

## Guarantees

This implementation guarantees that:

- a plan blocked at approval time has no outbox row;
- plan transition and outbox enqueue remain one MySQL transaction;
- Redis registry failure, Sense timeout, 5xx, authentication failure, or malformed response cannot fail open;
- a pre-dispatch safety failure cannot call MQTT;
- a terminal safety failure keeps `commandId` feedback correlation;
- command redelivery cannot bypass the existing Redis idempotency state;
- existing Cortex Kafka transactions, stable `eventId` keys, outbox delivery, ACK correlation, and Flyway-only schema ownership remain unchanged.

## Limits

- Device status is device-reported information and does not prove the physical state of the equipment.
- Without MQTT authentication and TLS, an attacker with broker access may forge status messages.
- Freshness must be tuned to the actual device heartbeat interval and network characteristics.
- Redis failure intentionally blocks valid commands as well as unsafe commands.
- The pre-dispatch recheck reduces but cannot completely eliminate a state change after the final check and before physical actuation.
- Manufacturer-specific validation is only as complete as the installed Device Adapter / `DeviceCapabilityResolver` implementation.
- This gate does not replace electrical interlocks, emergency stops, local controller limits, or other physical safety controls.
