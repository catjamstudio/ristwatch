from pathlib import Path

from app.models.telemetry import HealthState
from app.rist.parser import RistStatsParser


def test_parses_receiver_stats_fixture() -> None:
    payload = (Path(__file__).parent / "fixtures" / "receiver_stats.json").read_text(encoding="utf-8")
    snapshot = RistStatsParser().parse(payload, "test-ingest")

    assert snapshot.stream_id == "test-ingest"
    assert snapshot.status == HealthState.HEALTHY
    assert snapshot.bitrate_bps == 5_210_288
    assert snapshot.rtt_ms == 18.6
    assert snapshot.retries_bps == 31_742
    assert snapshot.buffer_ms == 1904
    assert snapshot.peers[0].cname == "BELABOX"


def test_rejects_non_object_json() -> None:
    try:
        RistStatsParser().parse("[]", "test-ingest")
    except ValueError as error:
        assert "JSON object" in str(error)
    else:
        raise AssertionError("Expected ValueError")

