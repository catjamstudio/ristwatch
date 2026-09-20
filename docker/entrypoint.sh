#!/bin/sh
set -eu

mkdir -p /config/logs
if [ ! -f /config/config.yaml ]; then
  cp /app/config/default.yaml /config/config.yaml
fi

if [ -n "${RISTWATCH_RIST_USERNAME:-}" ] && [ -n "${RISTWATCH_RIST_PASSWORD:-}" ]; then
  umask 077
  ristsrppasswd "$RISTWATCH_RIST_USERNAME" "$RISTWATCH_RIST_PASSWORD" | tail -n 1 > /config/ristwatch.srp
fi

exec uvicorn app.main:app --app-dir /app/backend --host 0.0.0.0 --port 8080

