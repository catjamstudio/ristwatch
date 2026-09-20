from pydantic import BaseModel, Field

from .telemetry import TelemetrySnapshot


class StreamConfig(BaseModel):
    id: str
    name: str
    enabled: bool = True
    input_url: str
    buffer_ms: int = Field(default=1800, ge=0)


class StreamSnapshot(BaseModel):
    config: StreamConfig
    telemetry: TelemetrySnapshot

