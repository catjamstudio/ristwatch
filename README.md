# RISTWatch

RISTWatch is a self-hosted RIST ingest monitoring and management appliance designed for Unraid. This repository is a new application and does not modify, migrate, stop, or otherwise interact with an existing MooRIST installation.

## Current milestone — RISTWatch 0.5.0 (build 10)

The initial build provides:

- A FastAPI backend with health, system, stream, and WebSocket telemetry APIs.
- An independently testable parser for libRIST-style statistics.
- Configurable health-state calculation.
- A responsive React and TypeScript dashboard with live/stale state, bitrate history, relay status, system status, and peer identity.
- A single production Docker image containing the compiled UI, API, and libRIST tools.
- Persistent configuration under `/config`.
- Development defaults of `18081 -> 8080/tcp` and `5100 -> 5100/udp`.
- An initial Unraid Docker template and CI workflow.

Real libRIST process control is enabled with `RISTWATCH_RIST_ENABLED=true` and consumes native libRIST receiver statistics.

## Architecture

```text
Browser
  | HTTP + WebSocket
  v
FastAPI ---- Stream service ---- Telemetry collector
  |                                  |
  |                                  +-- mock source (current default)
  |                                  +-- libRIST parser/process adapter (next milestone)
  v
/config/config.yaml and /config/ristwatch.db
```

The frontend is compiled during the Docker build and served by FastAPI. Runtime configuration, logs, and future SQLite history are stored outside the replaceable image in `/config`.

## Directory structure

```text
backend/             FastAPI application and unit tests
frontend/            React, TypeScript, and Vite dashboard
config/              Safe default configuration
docker/              Container entrypoint and healthcheck
unraid/              Unraid Docker template
.github/workflows/   Tests and image build
```

## Local backend development

```bash
python -m venv .venv
.venv/Scripts/pip install -e "./backend[dev]"
set RISTWATCH_CONFIG_DIR=.local/config
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload --port 8080
```

On Linux or macOS, use `.venv/bin/` and `export RISTWATCH_CONFIG_DIR=.local/config`.

## Local frontend development

```bash
cd frontend
pnpm install
pnpm run dev
```

Vite proxies `/api` and `/ws` to `http://localhost:8080`.

## Docker

Build and run:

```bash
docker build -t ristwatch:dev .
docker compose up -d
```

Open `http://localhost:18081`. The Compose deployment publishes the web and production RIST ports on the local host.

Runtime data is written to `./.local/config` by the included Compose file. On Unraid, map `/mnt/user/appdata/ristwatch` to `/config` instead.

## Configuration

At first startup, `config/default.yaml` is copied to `/config/config.yaml`. Health thresholds are configuration, not application constants. Set `telemetry.mock: false` only after the libRIST process adapter is enabled and validated against real receiver output.

RIST credentials may be stored as the private runtime backup in `/config/config.yaml`:

```yaml
rist_auth:
  username: "YOUR_USERNAME"
  password: "YOUR_PASSWORD"
```

On Unraid this file is `/mnt/user/appdata/ristwatch/config.yaml`. Docker variables `RISTWATCH_RIST_USERNAME` and `RISTWATCH_RIST_PASSWORD`, when populated, override these file values. Keep real credentials out of Git and out of `config/default.yaml`.

Never commit usernames, passwords, encryption secrets, public IP addresses, or production stream configuration.

## API

- `GET /api/health`
- `GET /api/system`
- `GET /api/streams`
- `GET /api/streams/{id}`
- `WS /ws/telemetry`

Interactive API documentation is available at `/docs`.

## Tests

```bash
python -m pip install -e "./backend[dev]"
pytest backend/tests
cd frontend && pnpm install --frozen-lockfile && pnpm run build
docker build -t ristwatch:dev .
```

## Unraid

Use `unraid/ristwatch.xml` as the starting Community Applications-style template. Its defaults are intentionally separate from MooRIST:

- Web UI: host `18081` to container `8080/tcp`
- RIST ingest: host `2030` to container `2030/udp`
- RIST secondary: host `2031` to container `2031/udp`
- RIST relay: host `5556` to container `5556/udp`
- Appdata: `/mnt/user/appdata/ristwatch` to `/config`

The template provides the WebUI link and restores Unraid's Edit workflow when the container is created from the template. Existing CLI-created containers must be recreated from the template to regain those controls.

## Known limitations

- Telemetry is simulated until real libRIST output samples are captured.
- RIST subprocess lifecycle methods are defined but not started automatically.
- SQLite history and stream mutation endpoints are reserved for later milestones.
- Authentication for the Web UI is not implemented yet; bind it only to trusted networks.

## Recommended next task

Capture sanitized `ristreceiver -v 6` statistics from a test feed on UDP `5100`, add them as parser fixtures, and implement the managed receiver process without changing the existing MooRIST deployment.
