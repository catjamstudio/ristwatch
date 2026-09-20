export type HealthState = "healthy" | "degraded" | "unstable" | "offline";

export interface PeerTelemetry {
  id: string;
  cname: string | null;
  bitrate_bps: number;
  average_bitrate_bps: number;
  rtt_ms: number;
  average_rtt_ms: number;
  received_bytes: number;
}

export interface StreamSnapshot {
  config: {
    id: string;
    name: string;
    enabled: boolean;
    input_url: string;
    buffer_ms: number;
  };
  telemetry: {
    stream_id: string;
    timestamp: string;
    status: HealthState;
    bitrate_bps: number;
    average_bitrate_bps: number;
    rtt_ms: number;
    average_rtt_ms: number;
    peers: PeerTelemetry[];
    retries_bps: number;
    rejected_bps: number;
    buffer_ms: number;
    uptime_seconds: number;
  };
}

