FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iptables openssl util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
COPY requirements-ra1a.lock ./
RUN python -m pip install --no-cache-dir -r requirements-ra1a.lock
COPY pyproject.toml ./
COPY vrae ./vrae
COPY contracts ./contracts
COPY industry-packs ./industry-packs
COPY tests ./tests
RUN python -m pip install --no-deps --no-build-isolation -e '.[dev]'
COPY infra/ra1a/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//; s/--regid=65532/--regid=10003/; s@python scripts/verify_ra1a.py /tmp/verification@python -m pytest -q -s -p no:cacheprovider tests/browser/test_isolated_browser.py@' /entrypoint.sh \
    && chmod 755 /entrypoint.sh
ENV VRAE_ISOLATED_LAB=1 VRAE_BROWSER_LAB=1 PYTHONDONTWRITEBYTECODE=1
ENTRYPOINT ["/entrypoint.sh"]
