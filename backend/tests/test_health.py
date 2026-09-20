import pytest

from app.models.telemetry import HealthState
from app.services.health import HealthInputs, calculate_health


POLICY = {
    "degraded": {"max_rtt_ms": 180, "max_retry_ratio": 0.08, "min_bitrate_bps": 500_000},
    "unstable": {"max_rtt_ms": 450, "max_retry_ratio": 0.20, "min_bitrate_bps": 100_000},
}


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (HealthInputs(5_000_000, 25, 10_000, 1), HealthState.HEALTHY),
        (HealthInputs(5_000_000, 250, 10_000, 1), HealthState.DEGRADED),
        (HealthInputs(5_000_000, 600, 10_000, 1), HealthState.UNSTABLE),
        (HealthInputs(0, 0, 0, 0), HealthState.OFFLINE),
    ],
)
def test_calculate_health(inputs: HealthInputs, expected: HealthState) -> None:
    assert calculate_health(inputs, POLICY) == expected

