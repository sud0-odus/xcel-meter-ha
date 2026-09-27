ARG BUILD_FROM=ghcr.io/home-assistant/base-python:3.14-alpine3.24
FROM ${BUILD_FROM}

ENV PIP_BREAK_SYSTEM_PACKAGES=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/xcel-meter-ha

COPY pyproject.toml ./
COPY src ./src

RUN python3 -m pip install --no-cache-dir . \
    && rm -rf /root/.cache

COPY rootfs /

LABEL \
  org.opencontainers.image.title="Home Assistant App: Xcel Meter HA Diagnostic" \
  org.opencontainers.image.description="IEEE 2030.5 diagnostics for Xcel Energy Itron meters" \
  org.opencontainers.image.licenses="BSD-3-Clause"
