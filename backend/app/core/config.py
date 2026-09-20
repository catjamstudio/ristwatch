import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.models.stream import StreamConfig


@dataclass(frozen=True)
class AppConfig:
    config_dir: Path
    raw: dict[str, Any]
    streams: list[StreamConfig]

    @property
    def mock_telemetry(self) -> bool:
        return bool(self.raw.get("telemetry", {}).get("mock", True))

    @property
    def telemetry_interval(self) -> float:
        return float(self.raw.get("telemetry", {}).get("interval_seconds", 1))

    @property
    def health_policy(self) -> dict[str, Any]:
        return dict(self.raw.get("health", {}))


def load_config() -> AppConfig:
    config_dir = Path(os.getenv("RISTWATCH_CONFIG_DIR", "/config"))
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "logs").mkdir(exist_ok=True)
    config_file = config_dir / "config.yaml"

    if not config_file.exists():
        default_path = Path(os.getenv("RISTWATCH_DEFAULT_CONFIG", "/app/config/default.yaml"))
        if default_path.exists():
            shutil.copyfile(default_path, config_file)
        else:
            config_file.write_text("telemetry:\n  mock: true\nstreams: []\n", encoding="utf-8")

    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    streams = [StreamConfig.model_validate(item) for item in raw.get("streams", [])]
    return AppConfig(config_dir=config_dir, raw=raw, streams=streams)

