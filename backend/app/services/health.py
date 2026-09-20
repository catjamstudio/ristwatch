from dataclasses import dataclass
from typing import Any

from app.models.telemetry import HealthState


@dataclass(frozen=True)
class HealthInputs:
    bitrate_bps: int
    rtt_ms: float
    retries_bps: int
    peer_count: int


def calculate_health(inputs: HealthInputs, policy: dict[str, Any]) -> HealthState:
    if inputs.peer_count <= 0 or inputs.bitrate_bps <= 0:
        return HealthState.OFFLINE

    retry_ratio = inputs.retries_bps / max(inputs.bitrate_bps, 1)
    unstable = policy.get("unstable", {})
    degraded = policy.get("degraded", {})

    if (
        inputs.rtt_ms > float(unstable.get("max_rtt_ms", 450))
        or retry_ratio > float(unstable.get("max_retry_ratio", 0.20))
        or inputs.bitrate_bps < int(unstable.get("min_bitrate_bps", 100_000))
    ):
        return HealthState.UNSTABLE

    if (
        inputs.rtt_ms > float(degraded.get("max_rtt_ms", 180))
        or retry_ratio > float(degraded.get("max_retry_ratio", 0.08))
        or inputs.bitrate_bps < int(degraded.get("min_bitrate_bps", 500_000))
    ):
        return HealthState.DEGRADED

    return HealthState.HEALTHY

