FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

FROM python:3.12-slim-bookworm AS librist-build
ARG LIBRIST_VERSION=0.2.20
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential ca-certificates curl meson ninja-build pkg-config \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /build
RUN curl -fsSL "https://github.com/eerimoq/librist/archive/refs/tags/v${LIBRIST_VERSION}.tar.gz" -o librist.tar.gz \
    && tar -xzf librist.tar.gz \
    && mv "librist-${LIBRIST_VERSION}" librist
WORKDIR /build/librist
RUN meson setup out -Dbuiltin_lz4=true -Dbuiltin_cjson=true -Duse_mbedtls=true -Dbuilt_tools=true -Dtest=false \
    && meson compile -C out \
    && meson install -C out --destdir /install

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LD_LIBRARY_PATH=/usr/local/lib \
    RISTWATCH_CONFIG_DIR=/config \
    RISTWATCH_DEFAULT_CONFIG=/app/config/default.yaml

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=librist-build /install/ /

WORKDIR /app
COPY backend/ /app/backend/
RUN python -m pip install --no-cache-dir /app/backend
COPY config/ /app/config/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/healthcheck.sh /usr/local/bin/healthcheck.sh
COPY --from=frontend-build /build/frontend/dist/ /app/frontend/
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/healthcheck.sh \
    && mkdir -p /config/logs

EXPOSE 8080/tcp 2030/udp 2031/udp 5556/udp
VOLUME ["/config"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/usr/local/bin/healthcheck.sh"]
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]


