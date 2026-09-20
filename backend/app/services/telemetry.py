import asyncio
import json
import logging
import math
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path


from app.models.stream import StreamConfig, StreamSnapshot
from app.models.telemetry import PeerTelemetry, TelemetrySnapshot
from app.rist.parser import RistStatsParser
from app.rist.process_manager import RistProcessManager
from app.services.health import HealthInputs, calculate_health


logger = logging.getLogger(__name__)

_LIVE_SNAPSHOTS: dict[str, TelemetrySnapshot] = {}


class TelemetryService:
    def __init__(self, streams: list[StreamConfig], policy: dict, interval: float = 1, rist_enabled: bool = False, srp_file: str | None = None, stats_timeout: float = 3) -> None:
        self.streams = streams
        self.policy = policy
        self.interval = interval
        self.started_at = time.monotonic()
        # Keep live state at module scope so the stats listener and all API/
        # WebSocket service references in this process read the same snapshot.
        self._latest = _LIVE_SNAPSHOTS
        self.rist_enabled = rist_enabled
        self.srp_file = srp_file
        self.process = RistProcessManager()
        self.forwarder = RistProcessManager()
        self.parser = RistStatsParser(policy)
        self._reader_task: asyncio.Task | None = None
        self.stats_timeout = stats_timeout
        self._last_stats_at = 0.0
        self._stream_started_at: dict[str, float] = {}
        self._stats_transport: asyncio.DatagramTransport | None = None
        self._snapshot_file = Path(os.getenv("RISTWATCH_CONFIG_DIR", "/config")) / "live-telemetry.json"

    async def start(self) -> None:
        if not self.rist_enabled or not self.streams:
            return
        stream = self.streams[0]
        input_url = stream.input_url
        command = ["ristreceiver", "-i", input_url, "-o", "udp://127.0.0.1:10000", "-r", "127.0.0.1:5005", "-S", "1000", "-v", "6"]
        print(f"Starting RIST receiver for stream {stream.id}: {' '.join(command)}", flush=True)
        if self.srp_file and os.path.exists(self.srp_file):
            command.extend(["-F", self.srp_file])
        await self.process.start(command)
        forwarder_url = os.getenv("RISTWATCH_FORWARDER_URL", "rist://@:5556?cname=ristwatch-relay")
        await self.forwarder.start(["ristsender", "-v", "-1", "-i", "udp://127.0.0.1:10000", "-o", forwarder_url, "-p", os.getenv("RISTWATCH_PROFILE", "1")])
        self._reader_task = asyncio.create_task(self._read_receiver(stream.id))
        loop = asyncio.get_running_loop()
        protocol = _StatsProtocol(self, stream.id)
        self._stats_transport, _ = await loop.create_datagram_endpoint(
            lambda: protocol, local_addr=("127.0.0.1", 5005)
        )

    async def stop(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
        if self._stats_transport:
            self._stats_transport.close()
            self._stats_transport = None
        await self.process.stop()
        await self.forwarder.stop()

    async def _read_receiver(self, stream_id: str) -> None:
        async for line in self.process.output_lines():
            print(f"ristreceiver[{stream_id}]: {line}", flush=True)
            snapshot = self.parser.parse_log_line(line, stream_id)
            if snapshot:
                self._latest[stream_id] = snapshot
        print(f"ristreceiver[{stream_id}] exited; no further receiver telemetry will be available", flush=True)

    def snapshots(self) -> list[StreamSnapshot]:
        self._reload_persisted_snapshots()
        return [StreamSnapshot(config=stream, telemetry=self.snapshot(stream)) for stream in self.streams]

    def _reload_persisted_snapshots(self) -> None:
        if not self._snapshot_file.exists():
            return
        try:
            cached = json.loads(self._snapshot_file.read_text(encoding="utf-8"))
            for stream_id, candidate in cached.items():
                if isinstance(candidate, dict):
                    self._latest[stream_id] = TelemetrySnapshot.model_validate(candidate)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Failed to load persisted telemetry: {exc}", flush=True)

    def snapshot(self, stream: StreamConfig) -> TelemetrySnapshot:
        existing = self._latest.get(stream.id)
        if self._snapshot_file.exists():
            try:
                cached = json.loads(self._snapshot_file.read_text(encoding="utf-8"))
                candidate = cached.get(stream.id)
                if isinstance(candidate, dict):
                    persisted = TelemetrySnapshot.model_validate(candidate)
                    if existing is None or persisted.timestamp >= existing.timestamp:
                        existing = persisted
                        self._latest[stream.id] = persisted
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        if existing is not None and time.time() - existing.timestamp.timestamp() > self.stats_timeout:
            return TelemetrySnapshot(stream_id=stream.id)
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


    def ingest_stats(self, payload: bytes, stream_id: str) -> None:
        line = payload.decode("utf-8", errors="replace").strip()
        # libRIST sends both receiver-flow snapshots and cumulative counters.
        # Cumulative-only messages contain no peer/bitrate state and must not
        # overwrite the latest live receiver snapshot with OFFLINE.
        if '"flowinstant"' not in line:
            return
        try:
            snapshot = self.parser.parse_log_line(line, stream_id)
        except Exception as exc:  # keep the receiver alive while diagnosing external stats formats
            print(f"Failed to parse libRIST stats for {stream_id}: {type(exc).__name__}: {exc}; raw={line[:500]!r}", flush=True)
            return
        if snapshot is None:
            print(f"Ignored non-statistics receiver datagram for {stream_id}: {line[:500]}", flush=True)
            return
        self._latest[stream_id] = snapshot
        self._stream_started_at.setdefault(stream_id, time.monotonic())
        snapshot.uptime_seconds = int(time.monotonic() - self._stream_started_at[stream_id])
        try:
            self._snapshot_file.parent.mkdir(parents=True, exist_ok=True)
            cached = {}
            if self._snapshot_file.exists():
                cached = json.loads(self._snapshot_file.read_text(encoding="utf-8"))
            cached[stream_id] = snapshot.model_dump(mode="json")
            temporary = self._snapshot_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(cached), encoding="utf-8")
            temporary.replace(self._snapshot_file)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"Failed to persist telemetry for {stream_id}: {exc}", flush=True)
        self._last_stats_at = time.monotonic()
        print(
            f"Updated telemetry for {stream_id}: status={snapshot.status} "
            f"bitrate_bps={snapshot.bitrate_bps} peers={len(snapshot.peers)}",
            flush=True,
        )

    def _mock_snapshot(self, stream: StreamConfig) -> TelemetrySnapshot:
        elapsed = int(time.monotonic() - self.started_at)
        wave = math.sin(elapsed / 4)
        bitrate = int(5_200_000 + wave * 420_000)
        rtt = round(26 + abs(math.sin(elapsed / 7)) * 18, 1)
        retries = int(24_000 + abs(wave) * 19_000)
        peer = PeerTelemetry(
            id="mock-peer-1", cname="BELABOX", bitrate_bps=bitrate,
            average_bitrate_bps=5_180_000, rtt_ms=rtt,
            average_rtt_ms=31.4, received_bytes=bitrate * max(elapsed, 1) // 8,
        )
        status = calculate_health(
            HealthInputs(bitrate_bps=bitrate, rtt_ms=rtt, retries_bps=retries, peer_count=1),
            self.policy,
        )
        return TelemetrySnapshot(
            stream_id=stream.id, status=status, bitrate_bps=bitrate,
            average_bitrate_bps=5_180_000, rtt_ms=rtt, average_rtt_ms=31.4,
            peers=[peer], retries_bps=retries, rejected_bps=0,
            buffer_ms=stream.buffer_ms, uptime_seconds=elapsed,
        )


class _StatsProtocol(asyncio.DatagramProtocol):
    def __init__(self, service: TelemetryService, stream_id: str) -> None:
        self.service = service
        self.stream_id = stream_id

    def datagram_received(self, data: bytes, _addr: tuple[str, int]) -> None:
        print(f"Received libRIST stats datagram ({len(data)} bytes)", flush=True)
        self.service.ingest_stats(data, self.stream_id)


