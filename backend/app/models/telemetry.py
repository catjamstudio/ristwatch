from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNSTABLE = "unstable"
    OFFLINE = "offline"


class PeerTelemetry(BaseModel):
    id: str
    cname: str | None = None
    source_ip: str | None = None
    bitrate_bps: int = 0
    average_bitrate_bps: int = 0
    rtt_ms: float = 0
    average_rtt_ms: float = 0
    received_bytes: int = 0


class TelemetrySnapshot(BaseModel):
    stream_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: HealthState = HealthState.OFFLINE
    bitrate_bps: int = 0
    average_bitrate_bps: int = 0
    rtt_ms: float = 0
    average_rtt_ms: float = 0
    peers: list[PeerTelemetry] = Field(default_factory=list)
    retries_bps: int = 0
    rejected_bps: int = 0
    buffer_ms: float = 0
    uptime_seconds: int = 0

