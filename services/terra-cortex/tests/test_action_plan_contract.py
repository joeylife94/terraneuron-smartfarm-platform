from src.cloudevents_models import (
    ActionCategory,
    ActionType,
    Priority,
    create_action_plan_event,
)


def test_action_plan_payload_omits_optional_null_fields() -> None:
    event = create_action_plan_event(
        trace_id="trace-contract-test",
        farm_id="farm-A",
        target_asset_id="dehumidifier-01",
        action_category=ActionCategory.VENTILATION,
        action_type=ActionType.TURN_ON,
        reasoning="Humidity exceeds the configured threshold.",
        priority=Priority.MEDIUM,
        parameters={"duration_minutes": 20},
    )

    payload = event.model_dump(mode="json")

    assert payload["data"]["parameters"] == {"duration_minutes": 20}
    assert "estimated_impact" not in payload["data"]
    assert all(
        value is not None
        for value in payload["data"]["parameters"].values()
    )


def test_action_plan_payload_preserves_configured_parameters() -> None:
    event = create_action_plan_event(
        trace_id="trace-contract-test",
        farm_id="farm-A",
        target_asset_id="fan-01",
        action_category=ActionCategory.VENTILATION,
        action_type=ActionType.TURN_ON,
        reasoning="Temperature exceeds the configured threshold.",
        priority=Priority.HIGH,
        parameters={
            "duration_minutes": 60,
            "speed_level": "max",
            "intensity": 100,
        },
    )

    payload = event.model_dump(mode="json")

    assert payload["data"]["parameters"] == {
        "duration_minutes": 60,
        "speed_level": "max",
        "intensity": 100,
    }
    assert payload["data"]["priority"] == "high"
