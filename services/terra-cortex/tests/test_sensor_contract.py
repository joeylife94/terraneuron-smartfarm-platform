import math

import pytest
from pydantic import ValidationError

from src.models import SensorData


@pytest.mark.parametrize(
    "sensor_type",
    ["temperature", "humidity", "co2", "soilMoisture", "light"],
)
def test_supported_sensor_types_are_accepted(sensor_type: str) -> None:
    sensor = SensorData(
        farmId="farm-A",
        sensorType=sensor_type,
        value=25.0,
    )

    assert sensor.sensorType == sensor_type


def test_sensor_identity_is_trimmed() -> None:
    sensor = SensorData(
        farmId="  farm-A  ",
        sensorType="  temperature  ",
        value=25.0,
    )

    assert sensor.farmId == "farm-A"
    assert sensor.sensorType == "temperature"


@pytest.mark.parametrize("sensor_type", ["pressure", "soil_moisture", "", "TEMPERATURE"])
def test_unsupported_sensor_type_is_rejected(sensor_type: str) -> None:
    with pytest.raises(ValidationError, match="unsupported sensorType"):
        SensorData(
            farmId="farm-A",
            sensorType=sensor_type,
            value=25.0,
        )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_non_finite_sensor_value_is_rejected(value: float) -> None:
    with pytest.raises(ValidationError, match="finite number"):
        SensorData(
            farmId="farm-A",
            sensorType="temperature",
            value=value,
        )


def test_blank_farm_id_is_rejected() -> None:
    with pytest.raises(ValidationError, match="farmId must not be blank"):
        SensorData(
            farmId="   ",
            sensorType="temperature",
            value=25.0,
        )
