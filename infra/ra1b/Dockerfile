FROM python:3.11-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    sed -i 's@http://deb.debian.org@https://deb.debian.org@g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=1 -o Acquire::https::Timeout=30 update \
    && apt-get -o Acquire::Retries=1 -o Acquire::https::Timeout=30 install -y --no-install-recommends chromium chromium-sandbox iproute2 iptables util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10003 vrae-ipc && useradd -u 10001 -g 10003 -M browser
RUN mkdir /ipc && chown 10001:10003 /ipc && chmod 770 /ipc
RUN test "$(dpkg-query -W -f='${Version}' chromium)" = '156.0.8078.79-1~deb12u1'
ENV HOME=/tmp/profile
COPY infra/ra1b/preflight.py /opt/preflight.py
COPY infra/ra1b/agent.py /opt/agent.py
COPY infra/ra1b/kernel_probe.py /opt/kernel_probe.py
USER 10001:10003
ENTRYPOINT ["python", "/opt/agent.py"]
