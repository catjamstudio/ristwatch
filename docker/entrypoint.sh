#!/bin/sh
set -eu

mkdir -p /config/logs
if [ ! -f /config/config.yaml ]; then
  cp /app/config/default.yaml /config/config.yaml
fi

if [ -z "${RISTWATCH_RIST_USERNAME:-}" ] || [ -z "${RISTWATCH_RIST_PASSWORD:-}" ]; then
  eval "$(python - <<'PY'
import shlex, yaml
from pathlib import Path
data = yaml.safe_load(Path('/config/config.yaml').read_text()) or {}
auth = data.get('rist_auth', {}) or {}
print('export RISTWATCH_RIST_USERNAME=' + shlex.quote(str(auth.get('username', ''))))
print('export RISTWATCH_RIST_PASSWORD=' + shlex.quote(str(auth.get('password', ''))))
PY
)"
fi

if [ -n "${RISTWATCH_RIST_USERNAME:-}" ] && [ -n "${RISTWATCH_RIST_PASSWORD:-}" ]; then
  umask 077
  ristsrppasswd "$RISTWATCH_RIST_USERNAME" "$RISTWATCH_RIST_PASSWORD" | tail -n 1 > /config/ristwatch.srp
fi

exec uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port 8080

