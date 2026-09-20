import json
from collections.abc import Mapping
from typing import Any

from app.models.telemetry import PeerTelemetry, TelemetrySnapshot
from app.services.health import HealthInputs, calculate_health


class RistStatsParser:
    def __init__(self, health_policy: dict[str, Any] | None = None) -> None:
        self.health_policy = health_policy or {}

    def parse(self, payload: str | bytes | Mapping[str, Any], stream_id: str) -> TelemetrySnapshot:
        data = self._decode(payload)
        frame = self._find_stats_frame(data)
        stats = frame.get("stats", {}) if isinstance(frame.get("stats"), Mapping) else {}
        raw_peers = frame.get("peers", [])
        if isinstance(raw_peers, Mapping):
            raw_peers = list(raw_peers.values())

        peers = [self._parse_peer(peer) for peer in raw_peers if isinstance(peer, Mapping)]
        bitrate_bps = self._number(stats, "bitrate", "bitrate_payload")
        if not bitrate_bps:
            bitrate_bps = sum(peer.bitrate_bps for peer in peers)
        retries_bps = self._number(stats, "bitrate_retries")
        rtt_ms = max((peer.rtt_ms for peer in peers), default=0.0)

        health_inputs = HealthInputs(
            bitrate_bps=int(bitrate_bps),
            rtt_ms=float(rtt_ms),
            retries_bps=int(retries_bps),
            peer_count=len(peers),
        )
        return TelemetrySnapshot(
            stream_id=stream_id,
            status=calculate_health(health_inputs, self.health_policy),
            bitrate_bps=int(bitrate_bps),
            average_bitrate_bps=int(sum(peer.average_bitrate_bps for peer in peers)),
            rtt_ms=float(rtt_ms),
            average_rtt_ms=max((peer.average_rtt_ms for peer in peers), default=0.0),
            peers=peers,
            retries_bps=int(retries_bps),
            rejected_bps=int(self._number(stats, "bitrate_rejected")),
            buffer_ms=float(self._number(stats, "avg_buffer_time")),
        )

    def parse_log_line(self, line: str, stream_id: str) -> TelemetrySnapshot | None:
        json_start = line.find("{")
        if json_start < 0:
            return None
        try:
            return self.parse(line[json_start:], stream_id)
        except (ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _decode(payload: str | bytes | Mapping[str, Any]) -> Mapping[str, Any]:
        if isinstance(payload, Mapping):
            return payload
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", errors="replace")
        parsed = json.loads(payload.strip())
        if not isinstance(parsed, Mapping):
            raise ValueError("RIST statistics payload must be a JSON object")
        return parsed

    @classmethod
    def _find_stats_frame(cls, data: Mapping[str, Any]) -> Mapping[str, Any]:
        for key in ("flowinstant", "receiver-stats", "receiver_stats"):
            candidate = data.get(key)
            if isinstance(candidate, Mapping):
                return cls._find_stats_frame(candidate)
        return data

    @staticmethod
    def _number(data: Mapping[str, Any], *keys: str) -> float:
        for key in keys:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    continue
        return 0.0

    @classmethod
    def _parse_peer(cls, peer: Mapping[str, Any]) -> PeerTelemetry:
        stats = peer.get("stats")
        values = stats if isinstance(stats, Mapping) else peer
        return PeerTelemetry(
            id=str(peer.get("id", "unknown")),
            cname=str(peer["cname"]) if peer.get("cname") is not None else None,
            bitrate_bps=int(cls._number(values, "bitrate")),
            average_bitrate_bps=int(cls._number(values, "avg_bitrate")),
            rtt_ms=cls._number(values, "rtt"),
            average_rtt_ms=cls._number(values, "avg_rtt"),
            received_bytes=int(cls._number(values, "received_bytes")),
        )

