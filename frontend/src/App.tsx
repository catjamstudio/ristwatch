import { useEffect, useMemo, useState } from "react";
import type { RelayStatus, StreamSnapshot, SystemStatus } from "./types";

const formatMbps = (value: number) => `${(value / 1_000_000).toFixed(2)} Mbps`;
const formatSeconds = (value: number) => {
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const seconds = value % 60;
  return [hours, minutes, seconds].map((part) => String(part).padStart(2, "0")).join(":");
};

function App() {
  const [streams, setStreams] = useState<StreamSnapshot[]>([]);
  const [history, setHistory] = useState<number[]>([]);
  const [connected, setConnected] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [relay, setRelay] = useState<RelayStatus | null>(null);
  const [system, setSystem] = useState<SystemStatus | null>(null);

  const mergeStreams = (incoming: StreamSnapshot[]) => {
    setStreams((current) => {
      const currentById = new Map(current.map((stream) => [stream.config.id, stream]));
      for (const stream of incoming) {
        const previous = currentById.get(stream.config.id);
        if (!previous || new Date(stream.telemetry.timestamp).getTime() >= new Date(previous.telemetry.timestamp).getTime()) {
          currentById.set(stream.config.id, stream);
        }
      }
      return incoming.map((stream) => currentById.get(stream.config.id) ?? stream);
    });
    const primary = incoming[0];
    if (primary) {
      setHistory((current) => [...current, primary.telemetry.bitrate_bps].slice(-60));
    }
  };

  useEffect(() => {
    const refresh = () => {
        fetch("/api/streams")
          .then((response) => response.json())
          .then((payload: StreamSnapshot[]) => mergeStreams(payload))
        .catch(() => undefined);
    };

    refresh();
    fetch("/api/relay").then((response) => response.json()).then(setRelay).catch(() => undefined);
    fetch("/api/system").then((response) => response.json()).then(setSystem).catch(() => undefined);
    const refreshTimer = window.setInterval(refresh, 1000);

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${window.location.host}/ws/telemetry`);
    socket.onopen = () => setConnected(true);
    socket.onclose = () => setConnected(false);
      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data) as { streams: StreamSnapshot[] };
        mergeStreams(payload.streams);
      };
    return () => {
      window.clearInterval(refreshTimer);
      socket.close();
    };
  }, []);

  const totals = useMemo(
    () => ({
      active: streams.filter((stream) => stream.telemetry.status !== "offline").length,
      bitrate: streams.reduce((sum, stream) => sum + stream.telemetry.bitrate_bps, 0),
      peers: streams.reduce((sum, stream) => sum + stream.telemetry.peers.length, 0),
      alerts: streams.filter((stream) => ["degraded", "unstable", "offline"].includes(stream.telemetry.status)).length,
    }),
    [streams],
  );

  const selected = streams.find((stream) => stream.config.id === selectedId) ?? streams[0];

  return (
    <main>
      <header className="topbar">
        <div>
          <span className="eyebrow">RIST CONTRIBUTION MONITOR</span>
          <h1>RISTWatch <small>0.5.0 · build 10</small></h1>
          {system && <div className="identity">Username: {system.rist_username || "not set"} · Password: {system.rist_password_mask || "not set"}</div>}
        </div>
        <div className="connection">
          <span className={`pulse ${connected ? "online" : "offline"}`} />
          {connected ? "Live telemetry" : "Reconnecting"}
        </div>
      </header>

      <section className="summary-grid">
        <Summary label="Active Ingests" value={String(totals.active)} />
        <Summary label="Total Bitrate" value={formatMbps(totals.bitrate)} />
        <Summary label="Connected Peers" value={String(totals.peers)} />
        <Summary label="Alerts" value={String(totals.alerts)} alert={totals.alerts > 0} />
      </section>

      <section className="panel table-panel">
        <div className="panel-heading">
          <div><span className="eyebrow">CURRENT STATE</span><h2>Ingests</h2></div>
          <span>{streams.length} configured</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Name</th><th>Status</th><th>Bitrate</th><th>RTT</th><th>Peers</th><th>Recovery</th><th>Buffer</th><th>Uptime</th></tr></thead>
            <tbody>
              {streams.map((stream) => (
                <tr key={stream.config.id} onClick={() => setSelectedId(stream.config.id)} className={selected?.config.id === stream.config.id ? "selected" : ""}>
                  <td><strong>{stream.config.name}</strong><small>{stream.config.id}</small></td>
                  <td><span className={`status ${stream.telemetry.status}`}>{stream.telemetry.status}</span></td>
                  <td>{formatMbps(stream.telemetry.bitrate_bps)}</td>
                  <td>{stream.telemetry.rtt_ms.toFixed(1)} ms</td>
                  <td>{stream.telemetry.peers.length}</td>
                  <td>{(stream.telemetry.retries_bps / 1000).toFixed(1)} Kbps</td>
                  <td>{stream.telemetry.buffer_ms.toFixed(0)} ms</td>
                  <td>{formatSeconds(stream.telemetry.uptime_seconds)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {selected && <StreamDetails stream={selected} history={history} />}
      <section className="details-grid">
        <RelayPanel relay={relay} />
        <SystemPanel system={system} />
      </section>
    </main>
  );
}

function Summary({ label, value, alert = false }: { label: string; value: string; alert?: boolean }) {
  return <article className="summary"><span>{label}</span><strong className={alert ? "alert" : ""}>{value}</strong></article>;
}

function StreamDetails({ stream, history }: { stream: StreamSnapshot; history: number[] }) {
  const telemetry = stream.telemetry;
  const ageSeconds = Math.max(0, Math.round((Date.now() - new Date(telemetry.timestamp).getTime()) / 1000));
  const live = telemetry.status !== "offline" && ageSeconds <= 3;
  return (
    <section className="details-grid">
      <article className="panel detail-panel">
        <div className="panel-heading"><div><span className="eyebrow">STREAM DETAIL</span><h2>{stream.config.name}</h2><small>{stream.config.id} · input UDP {stream.config.input_url.match(/:(\d+)/)?.[1] ?? "2030"}</small></div><span className={`status ${live ? "healthy" : "offline"}`}>{live ? "live" : "stale"}</span></div>
        <div className="metric-grid">
          <Metric label="Current bitrate" value={formatMbps(telemetry.bitrate_bps)} />
          <Metric label="Average bitrate" value={formatMbps(telemetry.average_bitrate_bps)} />
          <Metric label="Current RTT" value={`${telemetry.rtt_ms.toFixed(1)} ms`} />
          <Metric label="Average RTT" value={`${telemetry.average_rtt_ms.toFixed(1)} ms`} />
          <Metric label="Recovery" value={`${(telemetry.retries_bps / 1000).toFixed(1)} Kbps`} />
          <Metric label="Rejected" value={`${(telemetry.rejected_bps / 1000).toFixed(1)} Kbps`} />
        </div>
        <div className="telemetry-meta">Last telemetry: {new Date(telemetry.timestamp).toLocaleTimeString()} · {ageSeconds}s ago</div>
        <BitrateChart values={history} />
      </article>
      <article className="panel peers-panel">
        <div className="panel-heading"><div><span className="eyebrow">CONNECTIONS</span><h2>Peers</h2></div><span>{telemetry.peers.length}</span></div>
        {telemetry.peers.map((peer) => (
          <div className="peer" key={peer.id}>
            <div><strong>{peer.cname ?? peer.id}</strong><small>{peer.id}</small></div>
            <div><span>{formatMbps(peer.bitrate_bps)}</span><small>{peer.rtt_ms.toFixed(1)} ms RTT</small></div>
          </div>
        ))}
      </article>
    </section>
  );
}

function RelayPanel({ relay }: { relay: RelayStatus | null }) {
  return <article className="panel"><div className="panel-heading"><div><span className="eyebrow">RELAY</span><h2>Output</h2></div><span className={`status ${relay?.status === "running" ? "healthy" : "offline"}`}>{relay?.status ?? "unknown"}</span></div><div className="system-list"><div><span>Output URL</span><strong>{relay?.output_url ?? "—"}</strong></div><div><span>Receiver</span><strong>{relay?.receiver_running ? "running" : "stopped"}</strong></div><div><span>Sender</span><strong>{relay?.sender_running ? "running" : "stopped"}</strong></div></div></article>;
}

function SystemPanel({ system }: { system: SystemStatus | null }) {
  return <article className="panel"><div className="panel-heading"><div><span className="eyebrow">SYSTEM</span><h2>Status</h2></div><span className={`status ${system?.rist_enabled ? "healthy" : "offline"}`}>{system?.rist_enabled ? "real RIST" : "mock"}</span></div><div className="system-list"><div><span>RISTWatch</span><strong>{system?.version ?? "—"}</strong></div><div><span>Receiver / relay</span><strong>{system?.receiver_running && system?.sender_running ? "running" : "degraded"}</strong></div><div><span>Config reload</span><strong>{system?.last_config_reload ? new Date(system.last_config_reload * 1000).toLocaleString() : "—"}</strong></div></div></article>;
}

function BitrateChart({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="chart-placeholder"><span>Collecting bitrate history…</span></div>;
  const max = Math.max(...values, 1);
  const points = values.map((value, index) => `${(index / (values.length - 1)) * 100},${100 - (value / max) * 92}`).join(" ");
  return <div className="chart"><svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Bitrate history"><polyline points={points} fill="none" vectorEffect="non-scaling-stroke" /></svg><span>Bitrate history · last {values.length}s</span></div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>;
}

export default App;
