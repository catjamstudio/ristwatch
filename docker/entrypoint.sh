#!/bin/sh
set -eu

mkdir -p /config/logs
if [ ! -f /config/config.yaml ]; then
  cp /app/config/default.yaml /config/config.yaml
fi

exec uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port 8080

