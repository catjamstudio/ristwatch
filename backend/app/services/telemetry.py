import asyncio
import math
import os
import time
from collections.abc import AsyncIterator

from app.models.stream import StreamConfig, StreamSnapshot
from app.models.telemetry import PeerTelemetry, TelemetrySnapshot
from app.rist.parser import RistStatsParser
from app.rist.process_manager import RistProcessManager
from app.services.health import HealthInputs, calculate_health


class TelemetryService:
    def __init__(self, streams: list[StreamConfig], policy: dict, interval: float = 1, rist_enabled: bool = False, srp_file: str | None = None) -> None:
        self.streams = streams
        self.policy = policy
        self.interval = interval
        self.started_at = time.monotonic()
        self._latest: dict[str, TelemetrySnapshot] = {}
        self.rist_enabled = rist_enabled
        self.srp_file = srp_file
        self.process = RistProcessManager()
        self.parser = RistStatsParser(policy)
        self._reader_task: asyncio.Task | None = None

    async def start(self) -> None:
        if not self.rist_enabled or not self.streams:
            return
        stream = self.streams[0]
        input_url = stream.input_url
        command = ["ristreceiver", "-i", input_url, "-o", "udp://127.0.0.1:10000", "-S", "1000", "-v", "6"]
        if self.srp_file and os.path.exists(self.srp_file):
            command.extend(["-F", self.srp_file])
        await self.process.start(command)
        self._reader_task = asyncio.create_task(self._read_receiver(stream.id))

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        await self.process.stop()

    async def _read_receiver(self, stream_id: str) -> None:
        async for line in self.process.output_lines():
            snapshot = self.parser.parse_log_line(line, stream_id)
            if snapshot:
                self._latest[stream_id] = snapshot

    def snapshots(self) -> list[StreamSnapshot]:
        return [StreamSnapshot(config=stream, telemetry=self.snapshot(stream)) for stream in self.streams]

    def snapshot(self, stream: StreamConfig) -> TelemetrySnapshot:
        existing = self._latest.get(stream.id)
        if existing is not None:
            return existing
        return self._mock_snapshot(stream) if not self.rist_enabled else TelemetrySnapshot(stream_id=stream.id)

    def get(self, stream_id: str) -> StreamSnapshot | None:
        stream = next((item for item in self.streams if item.id == stream_id), None)
        return StreamSnapshot(config=stream, telemetry=self.snapshot(stream)) if stream else None

    async def stream(self) -> AsyncIterator[list[StreamSnapshot]]:
        while True:
            if not self.rist_enabled:
                for configured_stream in self.streams:
                    self._latest[configured_stream.id] = self._mock_snapshot(configured_stream)
            yield self.snapshots()
            await asyncio.sleep(self.interval)

    def _mock_snapshot(self, stream: StreamConfig) -> TelemetrySnapshot:
        elapsed = int(time.monotonic() - self.started_at)
        wave = math.sin(elapsed / 4)
        bitrate = int(5_200_000 + wave * 420_000)
        rtt = round(26 + abs(math.sin(elapsed / 7)) * 18, 1)
        retries = int(24_000 + abs(wave) * 19_000)
        peer = PeerTelemetry(
            id="mock-peer-1",
            cname="BELABOX",
            bitrate_bps=bitrate,
            average_bitrate_bps=5_180_000,
            rtt_ms=rtt,
            average_rtt_ms=31.4,
            received_bytes=bitrate * max(elapsed, 1) // 8,
        )
        status = calculate_health(
            HealthInputs(bitrate_bps=bitrate, rtt_ms=rtt, retries_bps=retries, peer_count=1),
            self.policy,
        )
        return TelemetrySnapshot(
            stream_id=stream.id,
            status=status,
            bitrate_bps=bitrate,
            average_bitrate_bps=5_180_000,
            rtt_ms=rtt,
            average_rtt_ms=31.4,
            peers=[peer],
            retries_bps=retries,
            rejected_bps=0,
            buffer_ms=stream.buffer_ms,
            uptime_seconds=elapsed,
        )

