ARG BASE=python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
FROM ${BASE}
# Build dependencies only. Target tests run later with NetworkMode=none.
RUN command -v iptables >/dev/null || (apt-get update && apt-get install -y --no-install-recommends iproute2 iptables openssl util-linux && rm -rf /var/lib/apt/lists/*)
COPY requirements-ra1a.lock /tmp/requirements-ra1a.lock
RUN python -c 'import pytest,jsonschema,dns,h11' || python -m pip install --no-cache-dir -r /tmp/requirements-ra1a.lock
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/candidate VRAE_ISOLATED_LAB=1 R1A_ISOLATED_LAB=1
WORKDIR /candidate
ENTRYPOINT ["/bin/sh", "/candidate/integration/l2_launch/security/setup.sh"]
