FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    RISTWATCH_CONFIG_DIR=/config \
    RISTWATCH_DEFAULT_CONFIG=/app/config/default.yaml

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl rist-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/ /app/backend/
RUN python -m pip install --no-cache-dir /app/backend
COPY config/ /app/config/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/healthcheck.sh /usr/local/bin/healthcheck.sh
COPY --from=frontend-build /build/frontend/dist/ /app/frontend/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh \
    && mkdir -p /config/logs

EXPOSE 8080/tcp 5100/udp
VOLUME ["/config"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/usr/local/bin/healthcheck.sh"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
