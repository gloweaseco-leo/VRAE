FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iptables openssl util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY requirements-ra1a.lock ./
RUN python -m pip install --no-cache-dir -r requirements-ra1a.lock
COPY pyproject.toml ./
COPY vrae ./vrae
COPY apps/operator_console ./apps/operator_console
COPY contracts ./contracts
COPY industry-packs ./industry-packs
COPY tests ./tests
COPY scripts ./scripts
COPY docs/03-engineering/ra3c-independent-qa ./docs/03-engineering/ra3c-independent-qa
RUN python -m pip install --no-deps --no-build-isolation -e '.[dev]' && mkdir /lab
COPY infra/ra1a/entrypoint.sh /lab/entrypoint.sh
RUN sed -i 's/\r$//' /lab/entrypoint.sh && chmod 755 /lab/entrypoint.sh
ENV VRAE_ISOLATED_LAB=1 PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPYCACHEPREFIX=/tmp/pycache RUFF_CACHE_DIR=/tmp/ruff-cache MYPY_CACHE_DIR=/tmp/mypy-cache
ENTRYPOINT ["/lab/entrypoint.sh"]
